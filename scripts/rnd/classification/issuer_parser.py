#!/usr/bin/env python3
"""
issuer_parser.py — extract the ISSUING AGENCIES of each document (文号 / 发文机关 parser).

WHY THIS EXISTS
---------------
Research-agenda Q7 (joint issuance / inter-agency coordination, the fragmented-
authority tradition) needs, per document, the list of agencies that signed it.
That signal is scattered across three fields of unequal quality:

  (a) `document_number` (文号): the issuer CODE prefix (发改环资〔2024〕1104号 -> 发改委,
      工信部联… -> MIIT as lead of a joint doc). Populated on ~22% of docs. It names
      the LEAD agency only; a joint doc carries the lead's 文号.
  (b) `publisher`: usually one name; gov.cn stores the full joint masthead
      space-separated ("交通运输部 工业和信息化部 财政部 …"); some sites use 、.
  (c) the TITLE head and the BODY HEADER line: "X部 Y部 Z总局关于…", or the
      elided form "商务部等9部门关于…" where 等N部门 is a direct coalition-size
      signal even though the names are not listed.

A naive multi-publisher LIKE found ~852 joint docs. This parser recovers the
coalition from all three sources, normalizes names to a canonical registry, and
materializes an additive table:

    doc_issuers(doc_id PK, issuers_json, n_issuers, lead_issuer, parse_source,
                inner_n_issuers)

  issuers_json     JSON list of canonical issuer names (lead first) — may be shorter
                   than n_issuers when the source elided names (等N部门).
  n_issuers        coalition size = max(len(issuers), N from 等N部门). 0 = unknown.
  lead_issuer      first signatory: the 文号 agency when mappable, else first name.
  parse_source     docnum | publisher | header | title | none  (which source gave
                   the LIST; 'docnum' means only the lead was recoverable).
  inner_n_issuers  for FORWARDING notices (转发/批转), the coalition size of the
                   forwarded document (e.g. 省政府办公厅转发省教育厅等7部门…) — the
                   forwarder is this doc's (single) issuer; the inner coalition
                   belongs to the forwarded text and is kept here for the caveat.

NORMALIZATION reuses `analyze.py` (split_formal_ref / normalize_formal_ref) and
`scripts/rnd/citations/extract_citations.py` (_norm_title) rather than new regexes.

USAGE (on the droplet, repo root):
    python3 scripts/rnd/classification/issuer_parser.py --dry-run --limit 2000
    python3 scripts/rnd/classification/issuer_parser.py --sample 40 --seed 7   # validation dump
    python3 scripts/rnd/classification/issuer_parser.py                        # full write
    python3 scripts/rnd/classification/issuer_parser.py --stats

WRITE DISCIPLINE: one transaction, busy_timeout=30s, only touches `doc_issuers`.
Check the nightly lock (/tmp/china-governance-daily-sync.lock.d) before a full write.

NIGHTLY: wired into `scripts/daily_sync.sh` Phase 2b (after compute_topics) as a FULL
rebuild (no --since-days, so parser fixes propagate to old rows). ~4 min on the
2-vCPU droplet; one transaction. Tests: `python3 tests/test_issuer_parser.py`.
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))

from analyze import split_formal_ref, normalize_formal_ref  # noqa: E402
from extract_citations import _norm_title  # noqa: E402,F401  (shared title folding, used by callers)

DB_PATH = ROOT / "documents.db"

# ---------------------------------------------------------------------------
# 1. Canonical registry of CENTRAL agencies: canonical -> aliases (any order).
#    Aliases are matched longest-first. Ministry general offices (X办公厅) fold
#    into X; 国务院办公厅 / 中共中央办公厅 stay distinct because they are distinct
#    signatories in the 公文 system.
# ---------------------------------------------------------------------------
REGISTRY = {
    "中共中央": ["中共中央", "党中央", "中央委员会"],
    "中共中央办公厅": ["中共中央办公厅", "中央办公厅", "中办"],
    "国务院": ["国务院"],
    "国务院办公厅": ["国务院办公厅", "国办"],
    "中央军委": ["中央军委", "中央军事委员会", "中央军委办公厅"],
    "全国人大常委会": ["全国人大常委会", "全国人民代表大会常务委员会", "全国人大"],
    "最高人民法院": ["最高人民法院", "最高法院", "最高法"],
    "最高人民检察院": ["最高人民检察院", "最高检察院", "最高检"],
    "中央宣传部": ["中央宣传部", "中宣部", "中共中央宣传部"],
    "中央组织部": ["中央组织部", "中组部", "中共中央组织部"],
    "中央政法委": ["中央政法委", "中央政法委员会"],
    "中央网信办": ["中央网信办", "国家网信办", "国家互联网信息办公室", "中央网络安全和信息化委员会办公室",
                   "中央网络安全和信息化领导小组办公室", "网信办"],
    "中央编办": ["中央编办", "中央机构编制委员会办公室"],
    "中央金融办": ["中央金融办", "中央金融委员会办公室"],
    "国家发展改革委": ["国家发展改革委", "国家发展和改革委员会", "发展改革委", "发改委", "国家发改委",
                   "国家计委", "国家发展计划委员会", "国家计划委员会", "国家经贸委", "国家经济贸易委员会"],
    "财政部": ["财政部"],
    "工业和信息化部": ["工业和信息化部", "工信部", "信息产业部"],
    "人力资源社会保障部": ["人力资源社会保障部", "人力资源和社会保障部", "人社部", "劳动保障部",
                     "劳动和社会保障部", "人事部"],
    "教育部": ["教育部", "国家教委", "国家教育委员会"],
    "科技部": ["科技部", "科学技术部"],
    "民政部": ["民政部"],
    "公安部": ["公安部"],
    "司法部": ["司法部"],
    "国家安全部": ["国家安全部"],
    "自然资源部": ["自然资源部", "国土资源部", "国土部"],
    "生态环境部": ["生态环境部", "环境保护部", "环保部", "国家环保总局", "国家环境保护总局", "国家环境保护部"],
    "住房城乡建设部": ["住房城乡建设部", "住房和城乡建设部", "住建部", "建设部"],
    "交通运输部": ["交通运输部", "交通部"],
    "水利部": ["水利部"],
    "农业农村部": ["农业农村部", "农业部"],
    "商务部": ["商务部", "对外贸易经济合作部", "外经贸部"],
    "文化和旅游部": ["文化和旅游部", "文旅部", "文化部", "国家旅游局"],
    "国家卫生健康委": ["国家卫生健康委", "国家卫生健康委员会", "卫生健康委", "国家卫生计生委",
                   "国家卫生和计划生育委员会", "卫生部", "国家卫健委"],
    "退役军人事务部": ["退役军人事务部"],
    "应急管理部": ["应急管理部", "国家安全监管总局", "国家安全生产监督管理总局", "安监总局"],
    "中国人民银行": ["中国人民银行", "人民银行", "央行", "人行"],
    "审计署": ["审计署"],
    "国务院国资委": ["国务院国资委", "国资委", "国务院国有资产监督管理委员会"],
    "海关总署": ["海关总署"],
    "税务总局": ["税务总局", "国家税务总局"],
    "市场监管总局": ["市场监管总局", "国家市场监督管理总局", "国家市场监管总局", "工商总局",
                 "国家工商行政管理总局", "国家工商总局", "质检总局", "国家质检总局",
                 "国家质量监督检验检疫总局", "食品药品监管总局", "国家食品药品监督管理总局", "食药监总局"],
    "金融监管总局": ["金融监管总局", "国家金融监督管理总局", "国家金融监管总局", "银保监会", "中国银保监会",
                 "中国银行保险监督管理委员会", "银监会", "中国银监会", "保监会", "中国保监会"],
    "证监会": ["证监会", "中国证监会", "中国证券监督管理委员会"],
    "国家广电总局": ["国家广电总局", "国家广播电视总局", "广电总局", "国家新闻出版广电总局"],
    "体育总局": ["体育总局", "国家体育总局"],
    "国家统计局": ["国家统计局", "统计局"],
    "国家知识产权局": ["国家知识产权局", "知识产权局"],
    "国家医保局": ["国家医保局", "国家医疗保障局", "医保局"],
    "国家药监局": ["国家药监局", "国家药品监督管理局", "药监局"],
    "国家能源局": ["国家能源局", "能源局"],
    "国家数据局": ["国家数据局"],
    "国家林草局": ["国家林草局", "国家林业和草原局", "国家林业局", "林草局"],
    "国家粮食和物资储备局": ["国家粮食和物资储备局", "国家粮食局", "粮食和物资储备局", "粮食和储备局"],
    "国家邮政局": ["国家邮政局", "邮政局"],
    "中国民航局": ["中国民航局", "民航局", "中国民用航空局"],
    "国家铁路局": ["国家铁路局"],
    "国家中医药局": ["国家中医药局", "国家中医药管理局", "中医药管理局", "中医药局"],
    "国家疾控局": ["国家疾控局", "国家疾病预防控制局"],
    "国家外汇局": ["国家外汇局", "国家外汇管理局", "外汇局"],
    "国家乡村振兴局": ["国家乡村振兴局", "国务院扶贫办", "国务院扶贫开发领导小组办公室"],
    "国家移民局": ["国家移民局", "国家移民管理局"],
    "国家消防救援局": ["国家消防救援局"],
    "国家矿山安监局": ["国家矿山安监局", "国家矿山安全监察局", "国家煤矿安监局"],
    "国家机关事务管理局": ["国家机关事务管理局", "国管局"],
    "国家民委": ["国家民委", "国家民族事务委员会"],
    "国家宗教局": ["国家宗教局", "国家宗教事务局"],
    "国家国防科工局": ["国家国防科工局", "国防科工局"],
    "国家烟草局": ["国家烟草局", "国家烟草专卖局"],
    "中国气象局": ["中国气象局", "气象局"],
    "中国地震局": ["中国地震局"],
    "中国科协": ["中国科协", "中国科学技术协会"],
    "中国科学院": ["中国科学院", "中科院"],
    "中国工程院": ["中国工程院"],
    "社科院": ["中国社会科学院", "社科院"],
    "全国总工会": ["全国总工会", "中华全国总工会", "总工会"],
    "共青团中央": ["共青团中央", "团中央"],
    "全国妇联": ["全国妇联", "中华全国妇女联合会"],
    "中国残联": ["中国残联", "中国残疾人联合会"],
    "全国工商联": ["全国工商联", "中华全国工商业联合会"],
    "国家开发银行": ["国家开发银行", "国开行"],
    "国家国际发展合作署": ["国家国际发展合作署"],
    "国家信访局": ["国家信访局"],
    "国家版权局": ["国家版权局"],
    "国家新闻出版署": ["国家新闻出版署", "新闻出版署", "新闻出版总署"],
    "国家文物局": ["国家文物局"],
    "国家档案局": ["国家档案局"],
    "国家保密局": ["国家保密局"],
    "国家密码局": ["国家密码管理局", "国家密码局"],
    "中央党校": ["中央党校", "国家行政学院"],
    "国务院发展研究中心": ["国务院发展研究中心"],
    "国务院参事室": ["国务院参事室"],
    "国务院港澳办": ["国务院港澳办", "国务院港澳事务办公室"],
    "国务院台办": ["国务院台办", "国务院台湾事务办公室"],
    "国务院侨办": ["国务院侨办", "国务院侨务办公室"],
    "国务院食安办": ["国务院食品安全委员会办公室", "国务院食安办"],
    "国务院安委办": ["国务院安委会办公室", "国务院安委办", "国务院安全生产委员会办公室"],
    "国务院妇儿工委": ["国务院妇女儿童工作委员会", "国务院妇儿工委"],
    "国务院反垄断委员会": ["国务院反垄断委员会"],
    "外交部": ["外交部"],
    "国防部": ["国防部"],
    "国家外国专家局": ["国家外国专家局", "外专局"],
    "国家公务员局": ["国家公务员局"],
    "中央农办": ["中央农办", "中央农村工作领导小组办公室"],
    "中央财办": ["中央财办", "中央财经委员会办公室", "中央财经领导小组办公室"],
    "中央台办": ["中央台办"],
    "中央统战部": ["中央统战部", "中共中央统一战线工作部"],
    "中央纪委国家监委": ["中央纪委国家监委", "中央纪委", "国家监委"],
    "中央文明办": ["中央文明办", "中央精神文明建设指导委员会办公室"],
    "中央军委政治工作部": ["中央军委政治工作部"],
    "中央军委国防动员部": ["中央军委国防动员部"],
    "中国人民银行上海总部": ["中国人民银行上海总部"],
}

_ALIAS_TO_CANON = {}
for _canon, _aliases in REGISTRY.items():
    for _a in _aliases:
        _ALIAS_TO_CANON.setdefault(_a, _canon)
    _ALIAS_TO_CANON.setdefault(_canon, _canon)
_ALIASES_SORTED = sorted(_ALIAS_TO_CANON, key=len, reverse=True)

# ---------------------------------------------------------------------------
# 2. 文号 issuer-code prefixes -> canonical. Longest prefix wins. Central codes
#    only apply to central-level sites (公〔…〕 at a Shenzhen site is not 公安部).
#    Sub-national government codes are unambiguous across the corpus.
# ---------------------------------------------------------------------------
DOCNUM_CENTRAL = {
    "国发": "国务院", "国函": "国务院", "国办发": "国务院办公厅", "国办函": "国务院办公厅",
    "国办": "国务院办公厅", "中发": "中共中央", "中办发": "中共中央办公厅", "中办": "中共中央办公厅",
    "发改": "国家发展改革委", "计": "国家发展改革委",
    "财": "财政部", "工信": "工业和信息化部", "人社": "人力资源社会保障部",
    "教": "教育部", "国科": "科技部", "科": "科技部", "民": "民政部", "公": "公安部",
    "司": "司法部", "自然资": "自然资源部", "国土资": "自然资源部", "环": "生态环境部",
    "建": "住房城乡建设部", "交": "交通运输部", "水": "水利部", "农": "农业农村部",
    "商": "商务部", "文旅": "文化和旅游部", "文": "文化和旅游部", "国卫": "国家卫生健康委",
    "卫": "国家卫生健康委", "退役": "退役军人事务部", "应急": "应急管理部", "安监": "应急管理部",
    "银发": "中国人民银行", "银办发": "中国人民银行", "审": "审计署", "国资": "国务院国资委",
    "署": "海关总署", "税总": "税务总局", "国税": "税务总局", "国市监": "市场监管总局",
    "市监": "市场监管总局", "工商": "市场监管总局", "质检": "市场监管总局", "食药监": "市场监管总局",
    "金规": "金融监管总局", "金办": "金融监管总局", "银保监": "金融监管总局", "银监": "金融监管总局",
    "保监": "金融监管总局", "证监": "证监会", "广电": "国家广电总局", "体": "体育总局",
    "国统": "国家统计局", "国知": "国家知识产权局", "医保": "国家医保局", "药监": "国家药监局",
    "国能": "国家能源局", "国数": "国家数据局", "林": "国家林草局", "粮": "国家粮食和物资储备局",
    "国粮": "国家粮食和物资储备局",
    "国邮": "国家邮政局", "民航": "中国民航局", "国铁": "国家铁路局", "国中医药": "国家中医药局",
    "汇": "国家外汇局", "国疾控": "国家疾控局", "网信": "中央网信办", "中网办": "中央网信办",
    "法": "最高人民法院", "高检": "最高人民检察院", "气": "中国气象局", "科协": "中国科协",
    "总工": "全国总工会", "中青": "共青团中央", "妇": "全国妇联", "残联": "中国残联",
    "国防科工": "国家国防科工局", "外": "外交部", "矿安": "国家矿山安监局", "消防": "国家消防救援局",
    "国移": "国家移民局", "国密": "国家密码局", "国新出": "国家新闻出版署", "文物": "国家文物局",
    "国宗": "国家宗教局", "民委": "国家民委", "烟": "国家烟草局",
}
DOCNUM_SUBNATIONAL = {
    # provinces / provincial-level municipalities
    # 粤办函 is the GOVERNMENT office's letter series (997/1,010 corpus docs carry publisher
    # 广东省人民政府办公厅 and sign the body as such); only 粤办发 is the 两办 party+gov series.
    "粤府办": "广东省人民政府办公厅", "粤府": "广东省人民政府", "粤办函": "广东省人民政府办公厅",
    "粤办": "中共广东省委办公厅", "粤发": "中共广东省委",
    "沪府办": "上海市人民政府办公厅", "沪府": "上海市人民政府", "沪委办": "中共上海市委办公厅",
    "京政办": "北京市人民政府办公厅", "京政": "北京市人民政府",
    "苏政办": "江苏省人民政府办公厅", "苏政": "江苏省人民政府",
    "渝府办": "重庆市人民政府办公厅", "渝府": "重庆市人民政府",
    "黑政办": "黑龙江省人民政府办公厅", "黑政": "黑龙江省人民政府",
    "浙政办": "浙江省人民政府办公厅", "浙政": "浙江省人民政府",
    "鄂政办": "湖北省人民政府办公厅", "鄂政": "湖北省人民政府",
    "闽政办": "福建省人民政府办公厅", "闽政": "福建省人民政府",
    "辽政办": "辽宁省人民政府办公厅", "辽政": "辽宁省人民政府",
    "藏政办": "西藏自治区人民政府办公厅", "藏政": "西藏自治区人民政府",
    "宁政办": "宁夏回族自治区人民政府办公厅", "宁政": "宁夏回族自治区人民政府",
    "青政办": "青海省人民政府办公厅", "青政": "青海省人民政府",
    "川办": "四川省人民政府办公厅", "川府": "四川省人民政府",
    "鲁政办": "山东省人民政府办公厅", "鲁政": "山东省人民政府",
    "豫政办": "河南省人民政府办公厅", "豫政": "河南省人民政府",
    "湘政办": "湖南省人民政府办公厅", "湘政": "湖南省人民政府",
    "皖政办": "安徽省人民政府办公厅", "皖政": "安徽省人民政府",
    "赣府厅": "江西省人民政府办公厅", "赣府": "江西省人民政府",
    "津政办": "天津市人民政府办公厅", "津政": "天津市人民政府",
    "冀政办": "河北省人民政府办公厅", "冀政": "河北省人民政府",
    "晋政办": "山西省人民政府办公厅", "晋政": "山西省人民政府",
    "陕政办": "陕西省人民政府办公厅", "陕政": "陕西省人民政府",
    "云政办": "云南省人民政府办公厅", "云政": "云南省人民政府",
    "桂政办": "广西壮族自治区人民政府办公厅", "桂政": "广西壮族自治区人民政府",
    "琼府办": "海南省人民政府办公厅", "琼府": "海南省人民政府",
    "新政办": "新疆维吾尔自治区人民政府办公厅", "新政": "新疆维吾尔自治区人民政府",
    "吉政办": "吉林省人民政府办公厅", "吉政": "吉林省人民政府",
    "甘政办": "甘肃省人民政府办公厅", "甘政": "甘肃省人民政府",
    "黔府办": "贵州省人民政府办公厅", "黔府": "贵州省人民政府",
    "内政办": "内蒙古自治区人民政府办公厅", "内政": "内蒙古自治区人民政府",
    # prefecture cities
    "深府办": "深圳市人民政府办公厅", "深府": "深圳市人民政府", "深办": "中共深圳市委办公厅", "深发": "中共深圳市委",
    "穗府办": "广州市人民政府办公厅", "穗府": "广州市人民政府",
    "苏府办": "苏州市人民政府办公室", "苏府": "苏州市人民政府",
    "武政办": "武汉市人民政府办公厅", "武政": "武汉市人民政府",
    "杭政办": "杭州市人民政府办公厅", "杭政": "杭州市人民政府",
    "宁政办发": "南京市人民政府办公厅", "宁政发": "南京市人民政府",
    "惠府办": "惠州市人民政府办公室", "惠府": "惠州市人民政府",
    "珠府办": "珠海市人民政府办公室", "珠府": "珠海市人民政府",
    "揭府办": "揭阳市人民政府办公室", "揭府": "揭阳市人民政府",
    "中府办": "中山市人民政府办公室", "中府": "中山市人民政府",
    "江府办": "江门市人民政府办公室", "江府": "江门市人民政府",
    "阳府办": "阳江市人民政府办公室", "阳府": "阳江市人民政府",
    "韶府办": "韶关市人民政府办公室", "韶府": "韶关市人民政府",
    "河府办": "河源市人民政府办公室", "河府": "河源市人民政府",
    "佛府办": "佛山市人民政府办公室", "佛府": "佛山市人民政府",
    "东府办": "东莞市人民政府办公室", "东府": "东莞市人民政府",
    "湛府办": "湛江市人民政府办公室", "湛府": "湛江市人民政府",
    "茂府办": "茂名市人民政府办公室", "茂府": "茂名市人民政府",
    "肇府办": "肇庆市人民政府办公室", "肇府": "肇庆市人民政府",
    "梅府办": "梅州市人民政府办公室", "梅府": "梅州市人民政府",
    "清府办": "清远市人民政府办公室", "清府": "清远市人民政府",
    "潮府办": "潮州市人民政府办公室", "潮府": "潮州市人民政府",
    "云府办": "云浮市人民政府办公室", "云府": "云浮市人民政府",
}
# 汕府 is shared by 汕头 / 汕尾; resolved by site below.
_SITE_DISAMBIG = {
    ("汕府办", "shantou"): "汕头市人民政府办公室", ("汕府", "shantou"): "汕头市人民政府",
    ("汕府办", "shanwei"): "汕尾市人民政府办公室", ("汕府", "shanwei"): "汕尾市人民政府",
}
_CENTRAL_PREFIXES = sorted(DOCNUM_CENTRAL, key=len, reverse=True)
_SUBNAT_PREFIXES = sorted(DOCNUM_SUBNATIONAL, key=len, reverse=True)
_SUBNAT_CANON = set(DOCNUM_SUBNATIONAL.values()) | set(_SITE_DISAMBIG.values())


def parse_docnum(docnum, admin_level, site_key=""):
    """Return (lead_canonical_or_None, joint_flag) from a 文号. joint_flag is True
    when the code carries the 联 (joint) token (工信部联…, 发改办联…)."""
    if not docnum:
        return None, False
    dn = normalize_formal_ref(docnum)
    parts = split_formal_ref(dn)
    if not parts:
        return None, False
    prefix = re.sub(r"[\s（）()〔〕\[\]]", "", parts[0])
    if not prefix or prefix.startswith(("公告", "通告", "通知", "令", "第")):
        return None, False
    joint = "联" in prefix
    for p in ("汕府办", "汕府"):
        if prefix.startswith(p) and (p, site_key) in _SITE_DISAMBIG:
            return _SITE_DISAMBIG[(p, site_key)], joint
    for p in _SUBNAT_PREFIXES:
        if prefix.startswith(p):
            return DOCNUM_SUBNATIONAL[p], joint
    if admin_level == "central":
        for p in _CENTRAL_PREFIXES:
            if prefix.startswith(p):
                return DOCNUM_CENTRAL[p], joint
    return None, joint


# ---------------------------------------------------------------------------
# 3. Name tokenization + normalization (publisher / title head / body header).
# ---------------------------------------------------------------------------
_ORG_SUFFIX = (
    r"(?:办公厅|办公室|管理委员会|管委会|委员会|总局|总署|总队|总会|总工会|总公司|集团|公司|"
    r"中心|学院|大学|银行|分行|法院|检察院|工委|党委|省委|市委|区委|警备区|卫戍区|军区|军分区|人武部|指挥部|领导小组|联席会议|"
    r"局|厅|部|委|会|署|院|办|府|社|处|队|站|所|团)"
)
_NAME_RE = re.compile(r"^[一-鿿（）()·]{2,32}" + _ORG_SUFFIX + r"$")
_NOISE_IN_NAME = re.compile(
    r"关于|通知|印发|转发|批转|意见|办法|方案|公告|通告|决定|规定|贯彻|落实|实施|执行|开展|做好|同意|批复|报告|"
    r"公示|通报|征求|召开|主持|的|[0-9０-９]|年|月|日|号")
_ZW = re.compile(r"[​‌‍﻿ ]")  # zero-width / nbsp junk inside names
# unqualified self-references used by provincial/municipal portals: 省政府, 市政府办公室, 区委办
_GENERIC = re.compile(r"^(?:中共)?(省|市|区|县)(人民)?(政府|委)(办公厅|办公室)?$")
_LOCALITY = re.compile(r"^(?:中共)?([一-鿿]{2,3}(?:省|市|自治区|区|县|自治州|新区))")
_SEP = re.compile(r"[\s、，,;；　]+")  # never 和/及: 住房和城乡建设部, 人力资源和社会保障局
_PAREN_ALIAS = re.compile(r"[（(][^）)]{0,30}[）)]")
_OFFICE_TAIL = re.compile(r"(办公厅|办公室|秘书局)$")
_LOCAL_PREFIX = re.compile(
    r"(?:中共)?(?:[一-鿿]{2,3}(?:省|市|区|县|自治区|自治州|新区|特区)|省|市|区|县)")

_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
           "十": 10, "零": 0, "〇": 0}


def cn_to_int(s):
    s = s.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    if s.isdigit():
        return int(s)
    if "十" in s:
        a, _, b = s.partition("十")
        tens = _CN_NUM.get(a, 1) if a else 1
        return tens * 10 + (_CN_NUM.get(b, 0) if b else 0)
    if len(s) == 1:
        return _CN_NUM.get(s, 0)
    val = 0
    for ch in s:
        val = val * 10 + _CN_NUM.get(ch, 0)
    return val


_ETC_N = re.compile(r"等([一二两三四五六七八九十0-9０-９]{1,3})个?(?:部门|单位|部委|部门和单位|家单位|委办局|个部门)")
_ETC_OPEN = re.compile(r"等(?:有关)?(?:部门|单位|部委|委办局)")

_NON_AGENCY_PUBLISHERS = re.compile(
    r"网$|报$|日报|晚报|周刊|杂志|新闻|电视|广播|首都之窗|微报|微信|公众号|编辑部|新华社|通讯社|人民网|政府网|信息中心$|研究院$|研究所$|协会$|学会$|基金会$")


_SAFE_ALIAS = re.compile(r"国家|国务院|中共|中央|中国|全国|最高|总局$|总署$|部$|共青团|社科院|审计署|海关")
_LEVEL = {"level": "central"}  # set per document by parse_doc


def _alias_ok(alias):
    """A bare short alias (发改委, 医保局, 统计局) is only read as the CENTRAL agency on a
    central-level document; on a sub-national doc it is the local bureau, kept literal."""
    return _LEVEL["level"] == "central" or bool(_SAFE_ALIAS.search(alias))


def canon_name(tok):
    """Canonicalize one agency-name token. Returns None if it is not a plausible
    agency name. Central aliases map to the registry key; sub-national names keep
    a light short form (parenthetical aliases dropped, ministry 办公厅 folded)."""
    t = _ZW.sub("", _PAREN_ALIAS.sub("", tok)).split("/")[0].strip(" 　:：")
    if not t:
        return None
    if t in _ALIAS_TO_CANON and _alias_ok(t):
        return _ALIAS_TO_CANON[t]
    # X办公厅 / X办公室 of a central ministry -> X (not for 国务院/中共中央)
    m = _OFFICE_TAIL.search(t)
    if m and t[: m.start()] in _ALIAS_TO_CANON and _alias_ok(t[: m.start()]):
        return _ALIAS_TO_CANON[t[: m.start()]]
    # "中共X" party-organ prefix forms of registry aliases
    if t.startswith("中共") and t[2:] in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[t[2:]]
    if _NOISE_IN_NAME.search(t) or not _NAME_RE.match(t):
        return None
    if _NON_AGENCY_PUBLISHERS.search(t):
        return None
    return t


def _split_glued(tok):
    """Split a run of agency names written without separators. First consume
    registry aliases greedily; then split before each repeated locality prefix
    (广东省…局广东省…厅 -> two names)."""
    out, rest = [], tok
    while rest:
        hit = None
        for a in _ALIASES_SORTED:
            if rest.startswith(a) and _alias_ok(a):
                # must be followed by a boundary (end / another alias / locality) to avoid
                # chopping '国家发展改革委' into '国家发展改革委' + stray text
                tail = rest[len(a):]
                if tail.startswith(("办公厅", "办公室")):
                    tail = tail[3:]
                # boundary: end, or another alias. NOT a locality: 国家税务总局广东省税务局 is
                # ONE vertical-management bureau, not 税务总局 + 广东省税务局.
                if not tail or any(tail.startswith(b) for b in _ALIASES_SORTED):
                    hit, rest = a, tail
                    break
        if hit:
            out.append(_ALIAS_TO_CANON[hit])
            continue
        break
    if not rest:
        return out
    # locality-prefixed sub-national names glued together
    pieces, cur = [], ""
    i = 0
    while i < len(rest):
        m = _LOCAL_PREFIX.match(rest, i)
        if (m and i > 0 and cur and _NAME_RE.match(cur)
                and cur not in _ALIAS_TO_CANON and not cur.startswith(("国家", "中国", "中央"))):
            # a central prefix followed by a locality is a vertical bureau (人民银行广州分行)
            pieces.append(cur)
            cur = ""
        cur += rest[i]
        i += 1
    if cur:
        pieces.append(cur)
    for p in pieces:
        c = canon_name(p)
        if c:
            out.append(c)
        else:
            return None  # a non-name fragment poisons the token: reject the whole head
    return out


def parse_names(text):
    """Parse a separator-delimited (or glued) run of agency names. Returns a list
    of canonical names, or None when any token is not a plausible agency name
    (precision gate)."""
    # strip parenthetical aliases BEFORE splitting: "中央网信办等十部门秘书局（办公厅、综合司）"
    # must not be split on the 、 inside the parentheses
    text = _PAREN_ALIAS.sub("", _ZW.sub("", text or "")).strip(" 　:：")
    if not text:
        return None
    names = []
    for tok in _SEP.split(text):
        tok = tok.strip(" 　")
        if not tok:
            continue
        g = _split_glued(tok)
        if g and len(g) >= 2:          # a glued run of names (财政部国家税务总局)
            names.extend(g)
            continue
        c = canon_name(tok)
        if c:
            names.append(c)
        elif g:
            names.extend(g)
        else:
            return None
    # dedupe, keep order
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out or None


def parse_publisher(pub):
    if not pub or _NON_AGENCY_PUBLISHERS.search(pub):
        return None, 0
    p = pub.strip().rstrip("等")
    n_etc = 0
    m = _ETC_N.search(pub)
    if m:
        n_etc = cn_to_int(m.group(1))
        p = pub[: m.start()]
    elif pub.endswith("等") or _ETC_OPEN.search(pub):
        p = _ETC_OPEN.sub("", pub).rstrip("等")
        n_etc = -1  # open-ended: at least len+1
    names = parse_names(p)
    return names, n_etc


# head of a title / body header: everything before the first verb frame
_HEAD_CUT = re.compile(r"(关于|印发|联合印发|联合发布|联合开展|联合部署|部署|公布|发布|决定|公告|通告|令$)")
_FORWARD = re.compile(r"(转发|批转)")
_DOCNUM_LINE = re.compile(r"[一-鿿]{1,12}[〔\[（(【]?[0-9０-９]{4}[〕\]）)】]?\s*[0-9０-９]+\s*号")
_DATE_LINE = re.compile(r"[0-9０-９一二三四五六七八九〇○]{4}年[0-9０-９一二三四五六七八九十〇○]{1,3}月[0-9０-９一二三四五六七八九十〇○]{1,3}日")
_HTML_NOISE = re.compile(r"<[^>]+>|&[a-z]+;|class=\S+|\{[^}]*\}|\.[a-zA-Z_]+\s*\{|\S+:\s*[0-9]+px")


def _head_of(text, max_len=160):
    """Return (issuer_head, forwarded_head, n_etc_lead, n_etc_inner) from the start
    of a title/header string, or (None, None, 0, 0) if no 关于-type frame is found
    within max_len chars."""
    s = _HTML_NOISE.sub(" ", _ZW.sub("", text or ""))
    s = s.replace("　", " ").strip()
    # drop leading 文号 / date / label lines
    for _ in range(3):
        s2 = _DOCNUM_LINE.sub("", s, count=1) if _DOCNUM_LINE.match(s) else s
        s2 = _DATE_LINE.sub("", s2, count=1) if _DATE_LINE.match(s2) else s2
        s2 = re.sub(r"^(发文字号|文号|索引号|发布机构|名称|标题)[:：]?\s*", "", s2).strip()
        if s2 == s:
            break
        s = s2
    m = _HEAD_CUT.search(s[:max_len])
    fw = _FORWARD.search(s[:60])
    forwarded = None
    if fw and (not m or fw.start() <= m.start()):
        # "X转发Y等N部门…" (also titles with no 关于 at all)
        head = s[: fw.start()].strip(" 　:：|")
        forwarded = s[fw.end(): fw.end() + 100]
    elif m:
        head = s[: m.start()].strip(" 　:：|")
        # "X关于转发Y等N部门…" : the forwarded coalition sits AFTER 关于
        rest = s[m.end(): m.end() + 100]
        fw2 = _FORWARD.match(rest)
        if fw2:
            forwarded = rest[fw2.end():]
    else:
        return None, None, 0, 0
    n_lead = _etc_count(head)
    head = _ETC_N.sub("", head)
    head = _ETC_OPEN.sub("", head).rstrip("等")
    return head.strip(), forwarded, n_lead, _inner_count(forwarded)


def _inner_count(forwarded):
    """Coalition size of a FORWARDED document: explicit 等N; open 等部门 -> named+1;
    else the number of parseable names before the verb frame."""
    if not forwarded:
        return 0
    mc = _HEAD_CUT.search(forwarded)
    fhead = forwarded[: mc.start()] if mc else forwarded
    n = _etc_count(fhead)
    if n > 0:
        return n
    if "等" in fhead:
        fhead = fhead[: fhead.index("等")]
    elif "《" in fhead:
        fhead = fhead[: fhead.index("《")]
    names = parse_names(fhead) or []
    if n == -1:
        return len(names) + 1
    return len(names)


def _etc_count(s):
    if not s:
        return 0
    m = _ETC_N.search(s)
    if m:
        return cn_to_int(m.group(1))
    if _ETC_OPEN.search(s) or s.rstrip().endswith("等"):
        return -1
    return 0


def parse_header(title, body):
    """Issuers from the title head, then the body header line. Returns
    (names, n_etc, source, inner_n)."""
    best = (None, 0, "none", 0)
    for src, text in (("title", title), ("header", body)):
        head, forwarded, n_lead, n_inner = _head_of(text)
        if head is None:
            continue
        names = parse_names(head) if head else None
        if names:
            n = n_lead
            cand = (names, n, src, n_inner)
            # prefer the longer explicit list; a title with 等N beats a bare header;
            # a qualified name beats an unqualified 省政府-type self-reference
            if (best[0] is None or len(names) > len(best[0]) or (n > 0 and best[1] <= 0)
                    or (len(names) == len(best[0]) and _GENERIC.match(best[0][0]) and not _GENERIC.match(names[0]))):
                best = cand
        elif not head and forwarded and best[0] is None:
            best = (None, 0, "none", n_inner)
    return best


# ---------------------------------------------------------------------------
# 4. Per-document combination
# ---------------------------------------------------------------------------
_OWN_DOCNUM = re.compile(r"([一-鿿]{1,12})[〔\[（(【]((?:19|20)\d{2})[〕\]）)】]\s*(\d+)\s*号")


def _docnum_from_text(title, body_head):
    """Fallback when document_number is empty (75% of docs): the doc's OWN 文号 usually
    sits at the very start of the body (苏政发〔2008〕105号 省政府关于…) or trails the
    title in （…）. Only those own-number positions are trusted; a mid-text 文号 is a
    citation of some OTHER document."""
    b = _HTML_NOISE.sub(" ", _ZW.sub("", body_head or "")).strip()
    m = _OWN_DOCNUM.search(b[:60])
    if m and m.start() <= 25:
        return m.group(0)
    t = (title or "").rstrip(" ）)】]")
    m = _OWN_DOCNUM.search(t)
    if m and all(ch in ")）]】〕 " for ch in t[m.end():]):
        return m.group(0)
    return None


def _qualify(name, lead_dn, others):
    """Resolve an unqualified self-reference (省政府, 市政府办公室) to a full name using
    the 文号 lead or another named signer's locality. Returns None to DROP the generic
    when a 文号 lead already names the same organ family."""
    g = _GENERIC.match(name)
    if not g:
        return name
    tail = ("人民" if g.group(3) == "政府" else "") + g.group(3) + (g.group(4) or "")
    if g.group(3) == "委":
        tail = "委" + (g.group(4) or "")
    for cand in ([lead_dn] if lead_dn else []) + list(others):
        if cand and cand.endswith(tail) and not _GENERIC.match(cand):
            return cand
    if lead_dn:
        return None  # 珠府办〔…〕 + publisher "市政府办公室": the 文号 already names it
    for cand in others:
        lm = _LOCALITY.match(cand or "")
        if lm:
            return ("中共" if g.group(3) == "委" else "") + lm.group(1) + tail
    return name


def _fold_offices(names):
    """Drop X办公厅/X办公室 when X itself is also listed (the 文号 names 江门市人民政府, the
    portal's publisher field says 江门市人民政府办公室: one signatory, not two)."""
    base = set(names)
    out = []
    for n in names:
        m = _OFFICE_TAIL.search(n)
        if m and n[: m.start()] in base:
            continue
        out.append(n)
    return out


def parse_doc(title, docnum, publisher, body_head, admin_level, site_key=""):
    _LEVEL["level"] = admin_level
    lead_dn, joint_dn = parse_docnum(docnum, admin_level, site_key)
    if not lead_dn:
        dn2 = _docnum_from_text(title, body_head)
        if dn2:
            lead_dn, joint_dn = parse_docnum(dn2, admin_level, site_key)
    pub_names, pub_etc = parse_publisher(publisher)
    hdr_names, hdr_etc, hdr_src, inner_n = parse_header(title, body_head)

    # choose the LIST: longest explicit list wins; ties -> the masthead (title/header)
    # over `publisher`, which on portal sites is the site-wide publishing unit
    # (深圳市大鹏新区管理委员会) rather than the bureau that actually signed.
    cands = []
    if pub_names:
        cands.append((len(pub_names), 1, pub_names, pub_etc, "publisher"))
    if hdr_names:
        cands.append((len(hdr_names), 2, hdr_names, hdr_etc, hdr_src))
    issuers, n_etc, source = [], 0, "none"
    if cands:
        cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
        _, _, issuers, n_etc, source = cands[0]
        # 等N from ANY source counts (names may be elided in the chosen one)
        etcs = [c[3] for c in cands]
        n_etc = max(etcs) if max(etcs) > 0 else (-1 if -1 in etcs else 0)
    others = [n for c in cands for n in c[2]]
    issuers = [q for q in (_qualify(n, lead_dn, others) for n in issuers) if q]
    if lead_dn:
        if lead_dn in issuers:
            issuers.remove(lead_dn)
            issuers.insert(0, lead_dn)
        elif source == "none":
            issuers.insert(0, lead_dn)
        elif source == "publisher":
            # `publisher` is a portal field, so the 文号 agency outranks it; a parsed
            # MASTHEAD (title/header) outranks the 文号 — some sites store a CITED
            # number (中发〔2019〕17号) in document_number.
            if lead_dn in _SUBNAT_CANON and len(issuers) == 1 and n_etc == 0 and not joint_dn:
                # A sub-national 文号 vs ONE different portal name: the 文号 REPLACES it.
                # Unioning them manufactured phantom pairs (粤办函 + publisher
                # 广东省人民政府办公厅 -> 省委办公厅+省政府办公厅; joint-issuance.md §6a).
                # A docnum code never adds a signatory the body does not carry.
                issuers = [lead_dn]
            else:
                issuers.insert(0, lead_dn)
        if source == "none":
            source = "docnum"
    issuers = _fold_offices(list(dict.fromkeys(issuers)))
    n = len(issuers)
    if n_etc > 0:
        # "商务部等9部门" counts the named lead among the 9 in standard usage
        n = max(n, n_etc)
    elif n_etc == -1 and n < 2:
        # open "等部门" with no explicit list anywhere: at least one unnamed co-signer.
        # When another source lists >=2 names explicitly, that list IS the 等.
        n = n + 1
    if joint_dn and n < 2:
        n = 2  # 联 code: joint by construction, co-signers unnamed
    lead = issuers[0] if issuers else None
    return {"issuers": issuers, "n_issuers": n if issuers else 0, "lead_issuer": lead,
            "parse_source": source, "inner_n_issuers": inner_n}


# ---------------------------------------------------------------------------
# 5. DB driver
# ---------------------------------------------------------------------------
SELECT = """
SELECT d.id, d.site_key, s.admin_level, d.title, d.document_number, d.publisher,
       substr(COALESCE(d.body_text_cn, ''), 1, 400)
FROM documents d JOIN sites s USING(site_key)
WHERE s.admin_level NOT IN ('media', 'research')
"""

DDL = """
CREATE TABLE IF NOT EXISTS doc_issuers (
    doc_id INTEGER PRIMARY KEY,
    issuers_json TEXT NOT NULL,
    n_issuers INTEGER NOT NULL,
    lead_issuer TEXT,
    parse_source TEXT NOT NULL,
    inner_n_issuers INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_doc_issuers_n ON doc_issuers(n_issuers);
CREATE INDEX IF NOT EXISTS idx_doc_issuers_lead ON doc_issuers(lead_issuer);
"""


def iter_docs(conn, limit=None, since_days=None, sample=None, seed=0, ids=None):
    q = SELECT
    if ids:
        q += " AND d.id IN (%s)" % ",".join(str(int(i)) for i in ids)
    if since_days:
        q += f" AND d.crawl_timestamp >= datetime('now', '-{int(since_days)} days')"
    if sample:
        q += f" ORDER BY ((d.id * 2654435761 + {int(seed)}) % 1000003) LIMIT {int(sample)}"
    elif limit:
        q += f" LIMIT {int(limit)}"
    cur = conn.execute(q)
    while True:
        rows = cur.fetchmany(2000)
        if not rows:
            break
        yield from rows


def run(db, dry_run=False, limit=None, since_days=None):
    conn = sqlite3.connect(str(db), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    t0 = time.time()
    out, stats = [], {"docs": 0, "with_issuer": 0, "joint": 0, "src": {}}
    for row in iter_docs(conn, limit=limit, since_days=since_days):
        did, site, level, title, dn, pub, body = row
        r = parse_doc(title, dn, pub, body, level, site)
        stats["docs"] += 1
        if r["issuers"]:
            stats["with_issuer"] += 1
        if r["n_issuers"] >= 2:
            stats["joint"] += 1
        stats["src"][r["parse_source"]] = stats["src"].get(r["parse_source"], 0) + 1
        out.append((did, json.dumps(r["issuers"], ensure_ascii=False), r["n_issuers"],
                    r["lead_issuer"], r["parse_source"], r["inner_n_issuers"]))
    print(f"parsed {stats['docs']} docs in {time.time() - t0:.0f}s; "
          f"with >=1 issuer: {stats['with_issuer']} ({100 * stats['with_issuer'] / max(1, stats['docs']):.1f}%); "
          f"joint (n>=2): {stats['joint']}; sources: {stats['src']}")
    if dry_run:
        return
    conn.executescript(DDL)
    with conn:  # ONE transaction
        conn.executemany(
            "INSERT OR REPLACE INTO doc_issuers(doc_id, issuers_json, n_issuers, lead_issuer, parse_source, inner_n_issuers) "
            "VALUES (?,?,?,?,?,?)", out)
    conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
    conn.close()
    print(f"wrote {len(out)} rows to doc_issuers in {time.time() - t0:.0f}s")


def dump_sample(db, n, seed, ids=None):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for row in iter_docs(conn, sample=None if ids else n, seed=seed, ids=ids):
        did, site, level, title, dn, pub, body = row
        r = parse_doc(title, dn, pub, body, level, site)
        b = re.sub(r"\s+", " ", body or "")[:150]
        print(f"\n=== {did} [{site}/{level}]\n  T: {title[:110]}\n  N: {dn}\n  P: {pub}\n"
              f"  B: {b}\n"
              f"  -> {r['issuers']} n={r['n_issuers']} lead={r['lead_issuer']} src={r['parse_source']} inner={r['inner_n_issuers']}")


def show_stats(db):
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    for q in (
        "SELECT parse_source, COUNT(*) FROM doc_issuers GROUP BY 1 ORDER BY 2 DESC",
        "SELECT CASE WHEN n_issuers=0 THEN '0' WHEN n_issuers=1 THEN '1' WHEN n_issuers<5 THEN '2-4' "
        "WHEN n_issuers<10 THEN '5-9' ELSE '10+' END b, COUNT(*) FROM doc_issuers GROUP BY 1",
        "SELECT lead_issuer, COUNT(*) FROM doc_issuers WHERE n_issuers>=2 GROUP BY 1 ORDER BY 2 DESC LIMIT 15",
    ):
        print(q)
        for r in conn.execute(q):
            print("  ", r)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--since-days", type=int, help="only docs crawled in the last N days (nightly mode)")
    ap.add_argument("--sample", type=int, help="print a deterministic random validation sample and exit")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--ids", help="comma-separated doc ids to dump (validation)")
    ap.add_argument("--stats", action="store_true")
    a = ap.parse_args()
    if a.sample or a.ids:
        dump_sample(a.db, a.sample or 0, a.seed, ids=a.ids.split(",") if a.ids else None)
    elif a.stats:
        show_stats(a.db)
    else:
        run(a.db, dry_run=a.dry_run, limit=a.limit, since_days=a.since_days)


if __name__ == "__main__":
    main()
