#!/usr/bin/env python3
"""build_citation_crawl_queue.py — turn UNRESOLVED citation edges into a ranked,
actionable crawl queue.

WHY
---
Citation resolution sits at a ~51% ceiling that is COVERAGE-bound, not
matching-bound (see docs/working/missing-cited-docs.md and the coverage-tracker).
The ~219k unresolved edges (`citations.target_id IS NULL`) point overwhelmingly at
documents the corpus does NOT hold. Each unresolved edge is therefore a vote for a
document we should acquire: the most-frequently-cited missing document is the single
most valuable thing to crawl next, because ingesting it resolves the most dangling
edges (and fills the most holes in diffusion / policy-trace analyses).

This script aggregates the unresolved edges into a ranked "what to crawl next"
queue, grouped/tagged by the INFERRED issuing institution and cross-referenced
against the coverage docs so each row reads "acquiring this (from institution X,
which is already-crawled / blocked / never-attempted) would resolve N citations."

WHAT IT DOES
------------
1. Pulls unresolved edges (source_id, citation_type, target_level, target_ref).
2. Normalizes each target_ref into a distinct-document KEY, mirroring the resolver
   in scripts/rnd/citations/extract_citations.py:
     - formal (文号): key on the canonical issuer+〔year〕+N号 core (full-width digits
       folded, punctuation stripped).
     - named / llm (titles): key on the punctuation/bracket/PRC-prefix-folded title
       (using the inner 《》 title when present). named+llm share the title space.
   NOTE: formal (文号) clusters are NOT merged with title clusters (no reliable
   文号<->title link), so a doc cited both ways can surface as two rows — same
   behaviour as the existing missing-cited-docs snapshot.
3. DEMAND = number of DISTINCT source documents citing that key.
4. Filters out non-actionable refs (meeting/event names, foreign laws, refs too
   short/generic to locate). Keeps refs that name a real, locatable Chinese-gov
   document (has a 文号, a 《》 title, or a document-type suffix).
5. Infers the issuing institution — from the 文号 issuer prefix (the CJK before
   〔YYYY〕, e.g. 深发改 / 苏政办发 / 粤府) and from title agency cues (省/市/部/委/厅/局…),
   maps it to a known site / institution, and tags a coverage_status
   (have | blocked | residential | spa | never | party | foreign | unknown)
   grounded in docs/working/coverage-ledger.csv + coverage.csv + the live sites list.
6. Writes docs/working/citation-crawl-queue.csv ranked by demand, and prints a
   summary (top targets, institution rollup, resolvable headroom, blocked vs
   never-attempted split).

READ-ONLY. Works off citations + document_number/title only — no body scans.

USAGE
-----
  # Default: pull live edges from the droplet over ssh (read-only sqlite3):
  python3 scripts/rnd/discovery/build_citation_crawl_queue.py

  # Against a local DB copy:
  python3 scripts/rnd/discovery/build_citation_crawl_queue.py --db documents.db

  # Against a pre-exported TSV (source_id \t type \t target_level \t target_ref):
  python3 scripts/rnd/discovery/build_citation_crawl_queue.py --tsv unresolved.tsv

  --out PATH     override the output CSV path
  --top N        how many rows to print to stdout (default 30)
  --min-demand N only write rows with demand >= N (default 2; 1 = the full tail)
"""

import argparse
import csv
import os
import re
import subprocess
import sys
from collections import defaultdict

# --- repo root (scripts/rnd/discovery/ -> parents[3]) -----------------------
ROOT = os.path.dirname(os.path.abspath(__file__))
for _ in range(3):
    ROOT = os.path.dirname(ROOT)

DEFAULT_SSH = "root@104.236.88.45"
DEFAULT_REMOTE_DB = "/root/china-governance/documents.db"
DEFAULT_OUT = os.path.join(ROOT, "docs", "working", "citation-crawl-queue.csv")

# ---------------------------------------------------------------------------
# Normalization (mirrors scripts/rnd/citations/extract_citations.py)
# ---------------------------------------------------------------------------
_TITLE_STRIP = re.compile(
    r'[\s《》〈〉「」『』【】〔〕\[\]()（）“”‘’"\'、，,。．\.·・:：;；／/　]')
_PRC_PREFIX = "中华人民共和国"
_FULLWIDTH_DIGITS = {ord('０') + i: chr(ord('0') + i) for i in range(10)}


def _norm_title(s):
    s = _TITLE_STRIP.sub('', s or '')
    if s.startswith(_PRC_PREFIX):
        s = s[len(_PRC_PREFIX):]
    return s


def _agg_docnum(s):
    s = (s or "").translate(_FULLWIDTH_DIGITS)
    return re.sub(r'[^一-鿿0-9号]', '', s)


# canonical issuer+〔year〕+N号 core; group(1)=issuer prefix, (2)=year, (3)=num
_CORE_DOCNUM = re.compile(
    r'([一-鿿]{1,10})'
    r'[〔〈《（‘〚\[(]'
    r'((?:19|20)\d{2})'
    r'[〕〉》）’〛\])]'
    r'\s*(\d+)\s*号'
)
_INNER_TITLE = re.compile(r'《([^《》]{8,})》')


def _core_docnum_match(s):
    ms = list(_CORE_DOCNUM.finditer((s or "").translate(_FULLWIDTH_DIGITS)))
    return ms[-1] if ms else None


# ---------------------------------------------------------------------------
# Actionability filter
# ---------------------------------------------------------------------------
# Document-type suffixes: a title containing one of these names a real, locatable
# government document (not just a topic phrase).
_DOC_TYPES = ("办法", "规定", "条例", "通知", "方案", "意见", "规划", "细则",
              "决定", "规则", "标准", "纲要", "公告", "制度", "预案", "目录",
              "规程", "措施", "计划", "准则", "指南", "指引", "规范", "章程",
              "大纲", "要点", "清单", "名录", "批复", "通报", "安排", "决议",
              "命令", "规章", "方针", "细目", "办法（试行）", "条")
_DOCTYPE_RE = re.compile("|".join(map(re.escape, _DOC_TYPES)))

# Non-document event / meeting refs (drop when no 文号 and no 《》).
_EVENT_RE = re.compile(
    r'(会议|全会|大会|座谈会|研讨会|峰会|论坛|新闻发布会|电视电话会|工作会|动员会|部署会)$')

# Foreign / out-of-scope markers.
_FOREIGN_RE = re.compile(
    r'(美国|欧盟|欧洲联盟|联合国|世界贸易组织|世贸组织|WTO|OECD|日本|韩国|德国|英国|法国|新加坡|香港特别行政区基本法)')

# Generic / unlocatable phrases (whole ref).
_GENERIC = {
    "有关规定", "相关规定", "相关文件", "有关文件", "上级文件", "上级规定",
    "有关法律法规", "相关法律法规", "法律法规", "有关政策", "相关政策",
    "国家有关规定", "国家有关法律法规", "国家相关规定", "本办法", "本规定",
    "本条例", "有关要求", "相关要求", "上述规定", "党内法规",
}


def is_actionable(raw_ref, has_docnum, norm_key):
    """Keep refs that name a real, locatable Chinese-gov document."""
    ref = (raw_ref or "").strip()
    if has_docnum:
        return True, ""
    if not norm_key or len(norm_key) < 6:
        return False, "too-short/generic"
    if norm_key in {_norm_title(g) for g in _GENERIC} or ref in _GENERIC:
        return False, "generic-phrase"
    if _FOREIGN_RE.search(ref):
        return False, "foreign/out-of-scope"
    has_title = "《" in ref
    if not has_title and _EVENT_RE.search(ref):
        return False, "meeting/event"
    # Title-like: has 《》 OR ends/contains a document-type suffix.
    if has_title or _DOCTYPE_RE.search(ref):
        return True, ""
    return False, "not-document-like"


# ---------------------------------------------------------------------------
# Issuer / institution inference + coverage status
# ---------------------------------------------------------------------------
# Central-agency 文号 prefixes (longest-match). status grounded in the sites list
# and coverage-ledger.csv (have / blocked / spa / party).
CENTRAL_PREFIXES = [
    # (prefix, institution label, coverage_status)
    ("国办发", "State Council General Office (国务院办公厅)", "have"),
    ("国办函", "State Council General Office (国务院办公厅)", "have"),
    ("国办", "State Council General Office (国务院办公厅)", "have"),
    ("国函", "State Council (国务院)", "have"),
    ("国发", "State Council (国务院)", "have"),
    ("中办发", "CPC Central Committee General Office (中共中央办公厅)", "party"),
    ("中办", "CPC Central Committee General Office (中共中央办公厅)", "party"),
    ("中发", "CPC Central Committee (中共中央)", "party"),
    ("中组", "CPC Organization Dept (中央组织部)", "party"),
    ("中宣", "CPC Propaganda Dept (中央宣传部)", "party"),
    ("发改", "NDRC (国家发改委)", "have"),
    ("财", "Ministry of Finance (财政部)", "have"),
    ("环", "Ministry of Ecology & Environment (生态环境部)", "have"),
    ("工信部", "MIIT (工信部)", "have"),
    ("工信", "MIIT (工信部)", "have"),
    ("信部", "MIIT (工信部)", "have"),
    ("教", "Ministry of Education (教育部)", "have"),
    ("国科发", "Ministry of Science & Technology (科技部)", "have"),
    ("科", "Ministry of Science & Technology (科技部)", "have"),
    ("银发", "People's Bank of China (人民银行)", "have"),
    ("银办发", "People's Bank of China (人民银行)", "have"),
    ("税总", "State Taxation Administration (税务总局)", "have"),
    ("国税发", "State Taxation Administration (税务总局)", "have"),
    ("国税函", "State Taxation Administration (税务总局)", "have"),
    ("商", "Ministry of Commerce (商务部)", "have"),
    ("网信", "Cyberspace Administration (中央网信办)", "have"),
    ("医保发", "National Healthcare Security Admin (国家医保局)", "have"),
    ("医保", "National Healthcare Security Admin (国家医保局)", "have"),
    ("水", "Ministry of Water Resources (水利部)", "have"),
    ("交", "Ministry of Transport (交通运输部)", "have"),
    ("农", "Ministry of Agriculture & Rural Affairs (农业农村部)", "have"),
    ("司", "Ministry of Justice (司法部)", "have"),
    ("审计", "National Audit Office (审计署)", "have"),
    ("审", "National Audit Office (审计署)", "have"),
    ("统计", "National Bureau of Statistics (国家统计局)", "have"),
    ("国统字", "National Bureau of Statistics (国家统计局)", "have"),
    ("文物", "National Cultural Heritage Admin (国家文物局)", "have"),
    ("国中医药", "National Admin of TCM (国家中医药管理局)", "have"),
    ("中医药", "National Admin of TCM (国家中医药管理局)", "have"),
    ("应急", "Ministry of Emergency Management (应急管理部)", "have"),
    ("安监", "Ministry of Emergency Management (应急管理部)", "have"),
    ("林", "National Forestry & Grassland Admin (国家林草局)", "have"),
    ("民航", "Civil Aviation Administration (民航局)", "have"),
    ("邮", "State Post Bureau (国家邮政局)", "have"),
    ("证监", "China Securities Regulatory Commission (证监会)", "have"),
    ("外汇", "State Administration of Foreign Exchange (外汇局)", "have"),
    ("汇发", "State Administration of Foreign Exchange (外汇局)", "have"),
    ("国知发", "National IP Administration (国家知识产权局)", "have"),
    ("知识产权", "National IP Administration (国家知识产权局)", "have"),
    # BLOCKED / not-yet central agencies (datacenter-IP or WAF; see ledger)
    ("人社部", "Ministry of Human Resources & Social Security (人社部)", "blocked"),
    ("人社", "Ministry of Human Resources & Social Security (人社部)", "blocked"),
    ("劳社", "Ministry of Human Resources & Social Security (人社部)", "blocked"),
    ("建", "Ministry of Housing & Urban-Rural Development (住建部)", "blocked"),
    ("国卫", "National Health Commission (国家卫健委)", "blocked"),
    ("卫", "National Health Commission (国家卫健委)", "blocked"),
    ("公通字", "Ministry of Public Security (公安部)", "blocked"),
    ("公", "Ministry of Public Security (公安部)", "blocked"),
    ("民政", "Ministry of Civil Affairs (民政部)", "blocked"),
    ("民", "Ministry of Civil Affairs (民政部)", "blocked"),
    ("国土", "Ministry of Natural Resources (自然资源部)", "blocked"),
    ("自然资", "Ministry of Natural Resources (自然资源部)", "blocked"),
    ("署", "General Administration of Customs (海关总署)", "blocked"),
    ("食药监", "National Medical Products Admin (药监局)", "blocked"),
    ("国药监", "National Medical Products Admin (药监局)", "blocked"),
    ("药监", "National Medical Products Admin (药监局)", "blocked"),
    ("银保监", "National Financial Regulatory Admin (金融监管总局)", "spa"),
    ("保监", "National Financial Regulatory Admin (金融监管总局)", "spa"),
    ("银监", "National Financial Regulatory Admin (金融监管总局)", "spa"),
]

# Province single-char (文号) abbreviations -> (province, site_key, status).
# status grounded in coverage-ledger.csv (have/blocked/residential) + coverage.csv.
PROVINCE_ABBR = {
    "粤": ("Guangdong (广东)", "gd", "have"),
    "苏": ("Jiangsu (江苏)", "js", "have"),
    "沪": ("Shanghai (上海)", "sh", "have"),
    "京": ("Beijing (北京)", "bj", "have"),
    "黑": ("Heilongjiang (黑龙江)", "hlj", "have"),
    "鲁": ("Shandong (山东)", "shandong", "have"),
    "闽": ("Fujian (福建)", "fujian", "have"),
    "浙": ("Zhejiang (浙江)", "zj", "have"),
    "辽": ("Liaoning (辽宁)", "liaoning", "have"),
    "吉": ("Jilin (吉林)", "jilin", "have"),
    "湘": ("Hunan (湖南)", "hunan", "have"),
    "藏": ("Tibet (西藏)", "xizang", "have"),
    "渝": ("Chongqing (重庆)", "cq", "have"),
    # blocked (datacenter-IP / WAF)
    "晋": ("Shanxi (山西)", "shanxi", "blocked"),
    "皖": ("Anhui (安徽)", "anhui", "blocked"),
    "鄂": ("Hubei (湖北)", "hubei", "blocked"),
    "桂": ("Guangxi (广西)", "guangxi", "blocked"),
    "陕": ("Shaanxi (陕西)", "shaanxi", "blocked"),
    "秦": ("Shaanxi (陕西)", "shaanxi", "blocked"),
    "青": ("Qinghai (青海)", "qinghai", "blocked"),
    "豫": ("Henan (河南)", "henan", "blocked"),
    "云": ("Yunnan (云南)", "yunnan", "blocked"),
    "滇": ("Yunnan (云南)", "yunnan", "blocked"),
    "蒙": ("Inner Mongolia (内蒙古)", "neimenggu", "blocked"),
    # residential (reachable only from a CN/residential IP; config built)
    "冀": ("Hebei (河北)", "hebei", "residential"),
    "赣": ("Jiangxi (江西)", "jiangxi", "residential"),
    "琼": ("Hainan (海南)", "hainan", "residential"),
    "川": ("Sichuan (四川)", "sichuan", "residential"),
    "蜀": ("Sichuan (四川)", "sichuan", "residential"),
    "黔": ("Guizhou (贵州)", "guizhou", "residential"),
    "贵": ("Guizhou (贵州)", "guizhou", "residential"),
    "新": ("Xinjiang (新疆)", "xinjiang", "residential"),
    "津": ("Tianjin (天津)", "tianjin", "residential"),
    # never-attempted
    "甘": ("Gansu (甘肃)", "gansu", "never"),
    "陇": ("Gansu (甘肃)", "gansu", "never"),
    "宁": ("Ningxia (宁夏) [amb. Nanjing 宁]", "ningxia", "have"),
}

# Guangdong municipal 文号 abbreviations (all GD cities are crawled -> have).
GD_CITY_ABBR = {
    "深": ("Shenzhen (深圳)", "sz", "have"),
    "穗": ("Guangzhou (广州)", "gz", "have"),
    "珠": ("Zhuhai (珠海)", "zhuhai", "have"),
    "佛": ("Foshan (佛山)", "foshan", "blocked"),
    "惠": ("Huizhou (惠州)", "huizhou", "have"),
    "莞": ("Dongguan (东莞)", "dongguan", "blocked"),
    "中": ("Zhongshan (中山)", "zhongshan", "have"),
    "江": ("Jiangmen (江门)", "jiangmen", "have"),
    "肇": ("Zhaoqing (肇庆)", "zhaoqing", "blocked"),
    "汕": ("Shantou (汕头)", "shantou", "have"),
    "湛": ("Zhanjiang (湛江)", "zhanjiang", "blocked"),
    "韶": ("Shaoguan (韶关)", "shaoguan", "have"),
    "河": ("Heyuan (河源)", "heyuan", "have"),  # 河 ambiguous (Hebei/Henan handled first)
    "汕尾": ("Shanwei (汕尾)", "shanwei", "have"),
    "阳": ("Yangjiang (阳江)", "yangjiang", "have"),
    "云浮": ("Yunfu (云浮)", "yunfu", "have"),
    "揭": ("Jieyang (揭阳)", "jieyang", "have"),
    "潮": ("Chaozhou (潮州)", "chaozhou", "blocked"),
}


def infer_from_docnum(issuer):
    """Map a 文号 issuer prefix (e.g. 深发改, 苏政办发, 粤府) to
    (institution_label, site_or_group, coverage_status)."""
    if not issuer:
        return ("unknown", "", "unknown")
    # 1) Guangdong-city municipal prefixes (Shenzhen 深…, Guangzhou 穗…) — check
    #    the 2-char ones first, then single-char.
    for k in ("汕尾", "云浮"):
        if issuer.startswith(k):
            label, site, st = GD_CITY_ABBR[k]
            return (label, site, st)
    # 2) Central-agency prefixes (longest match).
    for pref, label, st in CENTRAL_PREFIXES:
        if issuer.startswith(pref):
            return (label, "", st)
    # 3) Province single-char abbreviations.
    c0 = issuer[0]
    if c0 in PROVINCE_ABBR:
        label, site, st = PROVINCE_ABBR[c0]
        return (label, site, st)
    if c0 in GD_CITY_ABBR:
        label, site, st = GD_CITY_ABBR[c0]
        return (label, site, st)
    return (f"issuer:{issuer}", "", "unknown")


# Title agency cues -> institution. Ordered; first hit wins.
_TITLE_AGENCY = [
    (re.compile(r'^(国务院办公厅)'), "State Council General Office (国务院办公厅)", "have"),
    (re.compile(r'^(国务院)'), "State Council (国务院)", "have"),
    (re.compile(r'(中共中央|中央办公厅|中办)'), "CPC Central Committee (中共中央)", "party"),
    (re.compile(r'(国家发展改革委|发展改革委|发改委)'), "NDRC (国家发改委)", "have"),
    (re.compile(r'(财政部)'), "Ministry of Finance (财政部)", "have"),
    (re.compile(r'(工业和信息化部|工信部)'), "MIIT (工信部)", "have"),
    (re.compile(r'(生态环境部|环境保护部)'), "Ministry of Ecology & Environment (生态环境部)", "have"),
    (re.compile(r'(教育部)'), "Ministry of Education (教育部)", "have"),
    (re.compile(r'(科学技术部|科技部)'), "Ministry of Science & Technology (科技部)", "have"),
    (re.compile(r'(中国人民银行|人民银行)'), "People's Bank of China (人民银行)", "have"),
    (re.compile(r'(国家税务总局|税务总局)'), "State Taxation Administration (税务总局)", "have"),
    (re.compile(r'(商务部)'), "Ministry of Commerce (商务部)", "have"),
    (re.compile(r'(网信办|网络安全和信息化)'), "Cyberspace Administration (网信办)", "have"),
    (re.compile(r'(国家医疗保障局|医疗保障局|医保局)'), "National Healthcare Security Admin (国家医保局)", "have"),
    (re.compile(r'(市场监督管理总局|市场监管总局)'), "SAMR (市场监管总局)", "have"),
    (re.compile(r'(国家知识产权局)'), "National IP Administration (国家知识产权局)", "have"),
    (re.compile(r'(人力资源社会保障部|人力资源和社会保障部|人社部)'),
     "Ministry of Human Resources & Social Security (人社部)", "blocked"),
    (re.compile(r'(住房和城乡建设部|住建部|建设部)'),
     "Ministry of Housing & Urban-Rural Development (住建部)", "blocked"),
    (re.compile(r'(国家卫生健康委|卫生健康委|卫生部|卫健委)'),
     "National Health Commission (卫健委)", "blocked"),
    (re.compile(r'(公安部)'), "Ministry of Public Security (公安部)", "blocked"),
    (re.compile(r'(民政部)'), "Ministry of Civil Affairs (民政部)", "blocked"),
    (re.compile(r'(自然资源部|国土资源部)'), "Ministry of Natural Resources (自然资源部)", "blocked"),
    (re.compile(r'(海关总署)'), "General Administration of Customs (海关总署)", "blocked"),
    (re.compile(r'(国家药品监督管理局|药品监督管理局|食品药品监督管理)'),
     "National Medical Products Admin (药监局)", "blocked"),
]

# Full province names -> the PROVINCE_ABBR key (so a title cue resolves to status).
_PROV_NAME = {
    "广东省": "粤", "江苏省": "苏", "上海市": "沪", "北京市": "京",
    "黑龙江省": "黑", "山东省": "鲁", "福建省": "闽", "浙江省": "浙",
    "辽宁省": "辽", "吉林省": "吉", "湖南省": "湘", "西藏自治区": "藏",
    "重庆市": "渝", "宁夏回族自治区": "宁", "山西省": "晋", "安徽省": "皖",
    "湖北省": "鄂", "广西壮族自治区": "桂", "陕西省": "陕", "青海省": "青",
    "河南省": "豫", "云南省": "云", "内蒙古自治区": "蒙", "河北省": "冀",
    "江西省": "赣", "海南省": "琼", "四川省": "川", "贵州省": "黔",
    "新疆维吾尔自治区": "新", "天津市": "津", "甘肃省": "甘",
}

# Municipal (市) names -> (label, site, status). GD cities + other crawled munis.
_CITY_NAME = {
    "深圳市": GD_CITY_ABBR["深"], "广州市": GD_CITY_ABBR["穗"],
    "珠海市": GD_CITY_ABBR["珠"], "东莞市": GD_CITY_ABBR["莞"],
    "佛山市": GD_CITY_ABBR["佛"], "惠州市": GD_CITY_ABBR["惠"],
    "中山市": GD_CITY_ABBR["中"], "江门市": GD_CITY_ABBR["江"],
    "肇庆市": GD_CITY_ABBR["肇"], "汕头市": GD_CITY_ABBR["汕"],
    "湛江市": GD_CITY_ABBR["湛"], "韶关市": GD_CITY_ABBR["韶"],
    "河源市": GD_CITY_ABBR["河"], "汕尾市": GD_CITY_ABBR["汕尾"],
    "阳江市": GD_CITY_ABBR["阳"], "云浮市": GD_CITY_ABBR["云浮"],
    "揭阳市": GD_CITY_ABBR["揭"], "潮州市": GD_CITY_ABBR["潮"],
    "茂名市": ("Maoming (茂名)", "maoming", "blocked"),
    "梅州市": ("Meizhou (梅州)", "meizhou", "blocked"),
    "清远市": ("Qingyuan (清远)", "qingyuan", "blocked"),
    # crawled municipalities outside Guangdong
    "苏州市": ("Suzhou (苏州)", "suzhou", "have"),
    "武汉市": ("Wuhan (武汉)", "wuhan", "have"),
    "杭州市": ("Hangzhou (杭州)", "hangzhou", "have"),
    "青岛市": ("Qingdao (青岛)", "qingdao", "have"),
    "沈阳市": ("Shenyang (沈阳)", "shenyang", "have"),
    "济南市": ("Jinan (济南)", "jinan", "have"),
}

# National-law short/long forms (no agency prefix). npc holds ~29k law *metadata*
# only (no body), so citations to these can't resolve to a body doc — they are an
# enrichment/backfill target, not a fresh crawl. Tagged status "law-db".
_LAW_RE = re.compile(r'(法|条例|实施条例|实施细则|实施办法)$')
_ADMIN_REG_HINT = re.compile(
    r'^(认证认可|治安管理|统计法|物业管理|信访|政府信息公开|残疾人|土地管理法'
    r'|城乡规划法|环境保护法|安全生产法|行政处罚|行政许可|行政强制|行政复议'
    r'|公司登记|个人独资企业|城市房地产|建设工程|价格法|反不正当竞争|产品质量'
    r'|消费者权益|税收征收管理|发票管理|会计|审计法|预算法|政府采购)')


def _resolve_region(name):
    """Map a Chinese province/city name to (label, site, status), or None."""
    if name in _PROV_NAME:
        label, site, st = PROVINCE_ABBR[_PROV_NAME[name]]
        return (label, site, st)
    if name in _CITY_NAME:
        return _CITY_NAME[name]
    return None


def infer_from_title(ref):
    """Infer institution + status from title agency cues."""
    for rx, label, st in _TITLE_AGENCY:
        if rx.search(ref):
            return (label, "", st)
    core = ref.lstrip('《〈「『【〔[(（“‘ 　')  # drop leading brackets/quotes
    # National law / administrative regulation (short-name or PRC-prefixed).
    if core.startswith(_PRC_PREFIX) or (_LAW_RE.search(core) and _ADMIN_REG_HINT.match(core)):
        return ("National law/admin regulation (全国人大/国务院 · npc)", "npc", "law-db")
    # Region name anywhere near the start (省/自治区/市), incl. 中共X省委 party cues.
    ref = core
    m = re.search(r'([一-鿿]{2,7}(?:省|自治区))', ref[:12])
    if m:
        r = _resolve_region(m.group(1))
        if r:
            party = "中共" in ref[:6]
            label, site, st = r
            return (("CPC " + label) if party else label,
                    site, "party" if party else st)
        return (f"province:{m.group(1)}", "", "unknown")
    # Known crawled cities first (exact prefix), then a minimal 2-3char+市 fallback.
    for city, val in _CITY_NAME.items():
        if ref.startswith(city):
            return val
    m = re.match(r'^([一-鿿]{1,3}?市)', ref)
    if m:
        r = _resolve_region(m.group(1))
        if r:
            return r
        return (f"city:{m.group(1)}", "", "unknown")
    return ("unknown", "", "unknown")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
SQL = ("SELECT source_id, citation_type, COALESCE(target_level,''), "
       "REPLACE(REPLACE(target_ref, char(9), ' '), char(10), ' ') "
       "FROM citations WHERE target_id IS NULL")


def rows_from_tsv(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 4:
                yield parts[0], parts[1], parts[2], "\t".join(parts[3:])


def rows_from_sqlite3_cli(cmd_prefix):
    """Run the read-only SELECT via a sqlite3 CLI invocation (local or over ssh)
    and stream tab-separated rows. `cmd_prefix` is the argv list up to (but not
    including) the SQL string."""
    proc = subprocess.run(cmd_prefix + [SQL], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"sqlite3 query failed: {proc.stderr.strip()}")
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            yield parts[0], parts[1], parts[2], "\t".join(parts[3:])


def load_rows(args):
    if args.tsv:
        return rows_from_tsv(args.tsv)
    if args.db:
        return rows_from_sqlite3_cli(
            ["sqlite3", "-separator", "\t", f"file:{args.db}?mode=ro"])
    # default: ssh to the droplet, run sqlite3 there (read-only)
    remote = (f"cd /root/china-governance && sqlite3 -separator '\t' "
              f"'file:{args.remote_db}?mode=ro' \"{SQL}\"")
    proc = subprocess.run(["ssh", args.ssh, remote], capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"ssh sqlite3 query failed: {proc.stderr.strip()}")
    out = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 4:
            out.append((parts[0], parts[1], parts[2], "\t".join(parts[3:])))
    return out


# ---------------------------------------------------------------------------
# Main aggregation
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--db", help="local SQLite path (opened read-only)")
    src.add_argument("--tsv", help="pre-exported TSV (source_id\\ttype\\tlevel\\tref)")
    ap.add_argument("--ssh", default=DEFAULT_SSH, help="ssh host for the live DB")
    ap.add_argument("--remote-db", default=DEFAULT_REMOTE_DB, help="remote DB path")
    ap.add_argument("--out", default=DEFAULT_OUT, help="output CSV path")
    ap.add_argument("--top", type=int, default=30, help="rows to print")
    ap.add_argument("--min-demand", type=int, default=2,
                    help="only write rows with demand >= N (default 2)")
    args = ap.parse_args()

    # key -> aggregate
    agg = {}   # key -> dict(display, sources set, types Counter, levels Counter,
               #             has_docnum, issuer, sample_ref)
    total_rows = 0
    dropped = defaultdict(int)

    for source_id, ctype, tlevel, raw_ref in load_rows(args):
        total_rows += 1
        raw_ref = (raw_ref or "").strip()
        if not raw_ref:
            dropped["empty"] += 1
            continue

        m = _core_docnum_match(raw_ref)
        # Decide the clustering key.
        if ctype == "formal" and m:
            core = f"{m.group(1)}〔{m.group(2)}〕{m.group(3)}号"
            key = ("F", _agg_docnum(core))
            display = core
            has_docnum = True
            issuer = m.group(1)
        elif ctype == "formal":
            # formal ref that didn't parse a clean core — key on aggressive docnum
            key = ("F", _agg_docnum(raw_ref))
            display = raw_ref
            has_docnum = bool(re.search(r'\d+\s*号', raw_ref))
            im = re.match(r'^\s*([一-鿿]{1,10})', raw_ref)
            issuer = im.group(1) if im else ""
        else:
            # named / llm -> title cluster (use inner 《》 title if present)
            inner = _INNER_TITLE.findall(raw_ref)
            title = inner[0] if inner else raw_ref
            nk = _norm_title(title)
            key = ("T", nk)
            display = title
            has_docnum = bool(m)
            issuer = m.group(1) if m else ""

        norm_key = key[1]
        ok, why = is_actionable(raw_ref, has_docnum, norm_key)
        if not ok:
            dropped[why] += 1
            continue

        rec = agg.get(key)
        if rec is None:
            rec = {"display": display, "sources": set(),
                   "types": defaultdict(int), "levels": defaultdict(int),
                   "has_docnum": has_docnum, "issuer": issuer,
                   "sample_ref": raw_ref, "is_formal": key[0] == "F"}
            agg[key] = rec
        rec["sources"].add(source_id)
        rec["types"][ctype] += 1
        if tlevel:
            rec["levels"][tlevel] += 1
        if has_docnum and not rec["has_docnum"]:
            rec["has_docnum"] = True
        if not rec["issuer"] and issuer:
            rec["issuer"] = issuer
        # prefer a shorter, cleaner display for title clusters
        if not rec["is_formal"] and len(display) < len(rec["display"]):
            rec["display"] = display

    # Build ranked queue.
    queue = []
    for key, rec in agg.items():
        demand = len(rec["sources"])
        if rec["is_formal"] or rec["issuer"]:
            label, site, status = infer_from_docnum(rec["issuer"])
            if label == "unknown" and not rec["is_formal"]:
                label, site, status = infer_from_title(rec["sample_ref"])
        else:
            label, site, status = infer_from_title(rec["sample_ref"])
        # dominant target level
        level = (max(rec["levels"].items(), key=lambda kv: kv[1])[0]
                 if rec["levels"] else "unknown")
        types = "+".join(f"{t}:{n}" for t, n in
                         sorted(rec["types"].items(), key=lambda kv: -kv[1]))
        queue.append({
            "normalized_ref": rec["display"],
            "demand": demand,
            "target_level": level,
            "citation_types": types,
            "inferred_issuer": rec["issuer"] or "",
            "inferred_institution": label,
            "inferred_site": site,
            "coverage_status": status,
            "kind": "formal" if rec["is_formal"] else "title",
        })

    queue.sort(key=lambda r: (-r["demand"], r["normalized_ref"]))

    # Write CSV.
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    written = [r for r in queue if r["demand"] >= args.min_demand]
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "normalized_ref", "demand", "kind", "target_level",
                    "citation_types", "inferred_issuer", "inferred_institution",
                    "inferred_site", "coverage_status"])
        for i, r in enumerate(written, 1):
            w.writerow([i, r["normalized_ref"], r["demand"], r["kind"],
                        r["target_level"], r["citation_types"],
                        r["inferred_issuer"], r["inferred_institution"],
                        r["inferred_site"], r["coverage_status"]])

    # ---- Summary ----------------------------------------------------------
    actionable_demand = sum(r["demand"] for r in queue)
    print(f"\nUnresolved edges read:        {total_rows:,}")
    print(f"Dropped (non-actionable):     {sum(dropped.values()):,}")
    for why, n in sorted(dropped.items(), key=lambda kv: -kv[1]):
        print(f"    {why:<22} {n:,}")
    print(f"Distinct actionable targets:  {len(queue):,}")
    print(f"Rows written (demand>={args.min_demand}):     {len(written):,}  -> {args.out}")
    print(f"Resolvable-citation headroom: {actionable_demand:,} "
          f"(sum of demand across actionable targets)")

    # coverage split (by demand headroom + by distinct target)
    by_status_demand = defaultdict(int)
    by_status_targets = defaultdict(int)
    for r in queue:
        by_status_demand[r["coverage_status"]] += r["demand"]
        by_status_targets[r["coverage_status"]] += 1
    print("\nHeadroom by coverage_status (demand / distinct targets):")
    for st in sorted(by_status_demand, key=lambda s: -by_status_demand[s]):
        print(f"    {st:<12} {by_status_demand[st]:>8,}  /  {by_status_targets[st]:>7,}")

    # institution rollup (top by demand)
    inst_demand = defaultdict(int)
    inst_status = {}
    for r in queue:
        inst_demand[r["inferred_institution"]] += r["demand"]
        inst_status[r["inferred_institution"]] = r["coverage_status"]
    print("\nTOP 30 institutions by resolvable demand:")
    print(f"    {'demand':>7}  {'status':<12} institution")
    for inst in sorted(inst_demand, key=lambda k: -inst_demand[k])[:30]:
        print(f"    {inst_demand[inst]:>7,}  {inst_status[inst]:<12} {inst}")

    print(f"\nTOP {args.top} highest-demand missing documents:")
    print(f"    {'#':>3} {'demand':>6}  {'status':<11} ref  [institution]")
    for i, r in enumerate(written[:args.top], 1):
        print(f"    {i:>3} {r['demand']:>6}  {r['coverage_status']:<11} "
              f"{r['normalized_ref'][:46]}  [{r['inferred_institution']}]")


if __name__ == "__main__":
    main()
