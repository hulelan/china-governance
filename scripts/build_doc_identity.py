#!/usr/bin/env python3
"""
build_doc_identity.py — the per-DOCUMENT identity layer: ONE nightly-rebuildable
side table `doc_identity` holding the five fields the replications showed were
inferred or per-site (docs/research/corpus-lessons.md Part A):

    A1 admin_level_doc   level of the document's ISSUER, not of the hosting site
    A2 instrument_id     canonical copy id shared by all mirrors of one text
    A3 genre             promulgation | implementing | explainer | readout | news | other
    A4 date_quality      good | crawl_stamped | missing   (body_scanned reserved, see below)
    A5 lead_issuer       canonical lead agency from `doc_issuers`

WHY A SIDE TABLE (design decision, not open)
--------------------------------------------
Updating a column on all ~320k `documents` rows nightly rewrites every row's
body overflow pages (the 2026-08-10 compute_scores lesson: ~5GB WAL, 78 min).
`doc_identity` is a narrow table keyed by doc_id, rebuilt in ONE transaction
(CREATE IF NOT EXISTS + DELETE + INSERT); every consumer does one join.

SCHEMA
------
    doc_identity(
        doc_id INTEGER PRIMARY KEY,
        admin_level_doc TEXT,   -- central|provincial|municipal|district|department|media|research
        level_source TEXT,      -- issuer|docnum|npc_publisher|title_cue|site
        instrument_id INTEGER,  -- canonical representative's doc id (own id when unique)
        instrument_role TEXT,   -- canonical|mirror|unique
        genre TEXT,             -- promulgation|implementing|explainer|readout|news|other
        date_quality TEXT,      -- good|crawl_stamped|body_scanned|missing
        lead_issuer TEXT,       -- from doc_issuers.lead_issuer (NULL if none)
        localized_of INTEGER    -- id of the IN-CHAIN higher text whose stem this doc
                                -- localizes (the genre flip's trigger); NULL otherwise
    ) + indexes on admin_level_doc, instrument_id, genre.
    The table is DROPPED and recreated on every build (schema changes need no migration).

DERIVATION RULES (rule-based, no LLM; header fields only — no body reads)
--------------------------------------------------------------------------
A1  admin_level_doc — first rule that fires wins, recorded in `level_source`:
    (0) media / research SITES: the site type IS the identity (a newspaper is not
        an issuer); level = site type, level_source = 'site'.
    (1) `issuer`: `doc_issuers.lead_issuer` through `level_of_name()`:
          central registry name (issuer_parser.REGISTRY) or a 国家/国务院/中央/全国/
          最高 head with no locality token            -> central
          地区/自治州 (prefecture-tier units)          -> municipal
          X区 / X县 / 新区 / 开发区 (not 自治区)        -> district
          X省 / X自治区 / 北京|上海|天津|重庆市 head     -> provincial
          X市 head                                     -> municipal
          bare 省… / 市… / 区… self-reference           -> provincial / municipal / district
        A bureau folds into its government's level (省厅 -> provincial, 市局 ->
        municipal): the memo's complaint is precisely that bureau SITES blur levels.
    (2) `docnum`: the 文号 prefix. issuer_parser.DOCNUM_SUBNATIONAL (粤府 / 深府 /
        苏政办 …) -> level_of_name(agency); then web.services.documents.
        ADMIN_LEVEL_PREFIXES (国发/国办 -> central, 深X区 -> district …); then
        issuer_parser.DOCNUM_CENTRAL — but ONLY on central sites (公〔…〕 at a
        Shenzhen site is the local 公安局, not 公安部), mirroring the parser.
    (3) `npc_publisher`: the national-laws site (`npc`) hosts ~28k local 人大
        instruments under a blanket 'central' site level. A doc whose
        classify_main_name is in NPC_NATIONAL_CATEGORIES (below) is central; otherwise its `publisher` (X省人大常委会 -> provincial, X市人大
        -> municipal) through level_of_name().
    (4) `title_cue`: the title HEAD (before 关于/印发/the first 《) through
        level_of_name(): 中华人民共和国…/国务院…/中共中央… -> central, 广东省人民
        政府关于… -> provincial, 深圳市龙华区… -> district. Head only, so a
        forwarding notice (转发广东省…) keeps the forwarder's level.
    (5) `site`: fallback to sites.admin_level — except the 13 `department` sites,
        which are all Shenzhen MUNICIPAL bureaus (crawlers/gkmlpt.py) and fall
        back to municipal; `department` therefore appears only if a new
        department site of unknown government is added.

A2  instrument_id — mirrors of one text share one id.
    key   = normalized instrument CORE of the title, reusing the citation matcher's
            exact-core tier (extract_citations._title_cores_of_title + _norm_title):
            the 《X》 inside an institutional promulgation wrapper (印发/发布/公布《X》
            的通知), the X of a bare 关于印发X的通知, the 关于… body after an issuer
            masthead, else the whole title minus status tags / news leads / 文号
            tails. Non-institutional wrappers ('北京发布《X》', flag 2) are news ABOUT
            X and do not key to X. Keys shorter than 6 normalized chars never pool.
    who   = promulgation + the untyped `other` residual pool together; implementing
            instruments (转发 / 实施方案 at a lower level — distinct acts) pool only
            with their own copies; explainer / readout / news are ABOUT an
            instrument, never a copy of it, and stay `unique`.
    where = only ACROSS sites: a key whose docs all sit on one site stays `unique`
            (a single site's near-duplicates are usually distinct items).
    when  = docs sharing a key are sorted by date and chained into editions: a gap
            of more than 400 days to the previous member starts a NEW edition —
            unless the doc's hosting SITE level is strictly LOWER than the current
            edition's level, in which case it is a late repost of that edition (a
            bureau cannot promulgate a new edition of a State Council text; 政府信
            息公开条例 re-posted by a 民政局 in 2017 belongs to the 2007 text, the
            2019 npc copy opens the 2019 revision). Undated docs join the key's
            only edition, else stay `unique`.
    LOCALIZED RE-ISSUANCE (2026-10-06): a doc is a MIRROR of an instrument only if
            its core is the instrument's core with NO locality / issuing-body prefix.
            深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知 shares
            the core of the State Council's 《推动…行动方案》 but is Shenzhen's OWN plan —
            the consumption-diffusion memo's key adoption signal, which must be a
            diffusion SOURCE, not a pooled mirror. Rule: a doc whose title names a
            sub-national locality (a 省/市/区/县 masthead before 关于/印发, or a
            <locality>X core) is a *localized re-issuance* whenever its stem (core minus
            the locality) also appears on a HIGHER-level member (central text, or a
            province above a city). It is then its own instrument — `unique`, or the
            canonical of its own local pool keyed (stem, locality) — with genre
            `implementing`, and never pools with the higher-level text. A bare《X》
            repost (no locality anywhere in the title) stays a mirror: 受权发布丨…印发《X》
            on Xinhua, or 国务院…《X》 re-posted by a ministry. Locality names come from
            issuer_parser.DOCNUM_SUBNATIONAL (the 文号 registry's agency names) plus the
            doc's own masthead; province-shaped names (X省 / X自治区) are always accepted.
    IN-CHAIN GENRE FLIP (2026-10-06, docs/working/qa-genre-flip.md): the `localized`
            flag above (which only keeps a doc OUT of the higher text's pool) fires on
            ANY higher-ranked same-stem member. The genre flip promulgation ->
            `implementing` is stricter: it fires only when a same-stem text exists in
            the doc's OWN jurisdictional chain — central, or its own province
            (data/city_province.csv), or for a district its own city / province — and
            the stem is not a self-government housekeeping genre every government
            writes for itself (GENERIC_STEM_RE: 议事规则, 制定地方性法规条例, 三定规定,
            政府工作规则 …). The QA hand-check put the broad rule at 80% precision with
            all 12 wrong flips out-of-chain or housekeeping (苏州市养犬管理条例 <- 天津市;
            深圳市人大常委会议事规则 <- 福建省); the in-chain rule scores 44/45. The
            trigger's id is persisted as `localized_of`. A locality the map does not
            know (false detections such as 转发市) never flips; the count is reported.
    canonical = promulgation genre > highest admin_level_doc > earliest date
                (first publication is the authoritative copy) > lowest id.
    `unique` docs carry their own id as instrument_id, so GROUP BY instrument_id
    works unconditionally. build_diffusion_events pools anchors by this id and uses
    the canonical member as the anchor representative.

A3  genre — title shape first, stored algo_doc_type second:
    explainer    解读 / 答记者问 / 一图读懂 / 图解 / 政策问答 / 解答 / 划重点 …
    readout      会议 / 召开 / 讲话 / 调研 / 座谈 / 会见 / 出席 / 主持 / 考察 / 致辞 /
                 强调 / 指出 … when the title is NOT an issuance frame
                 (build_diffusion_events.NONISSUE_RE is the ancestor of this rule)
    implementing SUB-NATIONAL level and 实施方案 / 实施意见 / 实施细则 / 实施办法 /
                 实施《X法》办法 / 变通规定 / 贯彻落实 / 转发…的通知 / 若干措施 in an
                 issuance frame (or algo_doc_type in IMPLEMENTING_GENRES, below)
    promulgation an issuance frame (印发/发布/公布《X》 with an institutional masthead,
                 关于…的通知/意见/办法/规定/…, X令, central 关于…的公告), a bare
                 法/条例/办法/规定 title, or algo_doc_type in {regulation, law, decree,
                 opinion, action_plan, policy_issuance, strategy, plan, work_plan,
                 decision, notice, subsidy, standard}. A 征求意见 draft is `other`.
    news         media sites, or 新闻 / 报道 / 快讯 / 发布会 / 记者 / 回应 / 反响 … cues,
                 or a non-institutional 《X》 lead (北京发布《X》)
    other        everything else (procurement, budgets, personnel, consultations,
                 local 公告, research-site reports/translations, and gov-site local
                 news that carries no cue — the known residual, ~half of `other`
                 on the hand-check samples)
    Hand-check precision (3 stratified 60-doc samples, 2026-10-06): A1 level 59/60
    and 59/60; A3 genre 50/60 → 53/60 → 53/60 before each round's fixes (the
    remaining misses are the uncued-news residual in `other`).
    A media reprint of an instrument (受权发布丨…印发《X》) is genre promulgation at
    level media — the diffusion `source_implementing` flag is the AND of the two.

A4  date_quality — per SITE, the industrial-policy memo's rule (docs/research/
    industrial-policy-targeting.md "Date-stamp exclusion"): a government site whose
    dated 2008+ documents are >=70% in the crawl year (2026) carries crawl dates,
    not publication dates; every doc on it is `crawl_stamped`. A >=100-doc floor
    reproduces the memo's 74-site universe (small sites cannot show a spread).
    (2026-10-06, SUPERSEDED) the year rule flagged shallow, recent-only first crawls whose
    dates are real (js_mzt / njd_jiangning / jcgov …: the pages' own <meta PubDate> and URL
    t-dates match the stored dates). The stamp is now measured where it would have to show:
    a site is `crawl_stamped` iff >=70% of the docs pulled on its modal (bulk) crawl day,
    >=20 of them, are dated ON that day — see the comment above crawl_stamped_sites(). The
    >=100-doc floor is kept. `missing` = no date_published. `body_scanned` is reserved: the
    crawlers do not record where a date came from, so it cannot be derived today. Else `good`.

A5  lead_issuer — doc_issuers.lead_issuer verbatim (the issuer field of record).

USAGE (repo root; the DB is the droplet's documents.db)
-------------------------------------------------------
    python3 scripts/build_doc_identity.py --self-test
    python3 scripts/build_doc_identity.py --dry-run          # compute + stats, no write
    python3 scripts/build_doc_identity.py --dry-run-flips    # broad vs in-chain flip counts + 30 flip-backs, read-only
    python3 scripts/build_doc_identity.py                    # full rebuild, one transaction
    python3 scripts/build_doc_identity.py --validate         # A1–A4 checks against known truth
    python3 scripts/build_doc_identity.py --sample 60 --seed 7   # stratified hand-check dump

WRITE DISCIPLINE: busy_timeout=30s, one transaction, only touches `doc_identity`.
Refuses to write while the nightly lock (/tmp/china-governance-daily-sync.lock.d)
exists unless --force. daily_sync.sh Phase 2b runs it with --force (it holds the
lock itself) after issuer_parser / compute_scores and before build_diffusion_events.
"""
import argparse
import os
import random
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(os.environ.get("CG_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "classification"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from extract_citations import (  # noqa: E402
    _norm_title, _title_cores_of_title, _WRAP_QUOTED, _WRAP_PLAIN, _MASTHEAD_PRE,
    _INST_SUFFIX, _STATUS_TAG, _NEWS_LEAD)
from issuer_parser import REGISTRY, DOCNUM_SUBNATIONAL, DOCNUM_CENTRAL  # noqa: E402
from build_diffusion_events import NONISSUE_RE  # noqa: E402
from genre_typer import clean_title, _TRAILING_ANNOT_RE  # noqa: E402

# The `npc` site (国家法律法规数据库, crawlers/npc.py) is tagged admin_level=central
# as a whole, but ~28k of its rows are provincial/municipal 人大 instruments
# (地方法规 + their amendment/repeal decisions + 法规性决定, which are ALL local
# 人大常委会 decisions — none starts with 全国人民代表大会). Only these categories
# (classify_main_name) are genuinely national-level instruments. (Moved here from
# build_diffusion_events, which now reads admin_level_doc instead.)
NPC_NATIONAL_CATEGORIES = frozenset({
    "宪法", "法律", "修正案", "法律解释", "行政法规", "监察法规",
    "有关法律问题和重大问题的决定",
    "修改、废止的决定（法律）", "修改、废止的决定（行政法规）",
    "高法司法解释", "高检司法解释", "联合发布司法解释", "修改、废止的决定（司法解释）",
})
# algo_doc_type labels that mark a sub-national doc as an implementing INSTRUMENT
# (diffusion-fidelity.md's implementing-instrument subset + the framework labels
# the typer also emits). NOT: explainer, announcement, report, publicity,
# commentary, interview, reply, circular, administrative, budget, procurement,
# personnel, consultation, application_guide, standard, review, request, other.
IMPLEMENTING_GENRES = frozenset({
    "action_plan", "work_plan", "policy_issuance", "opinion", "notice",
    "regulation", "decision", "strategy", "subsidy", "law", "decree", "plan",
})

try:  # web.services.documents pulls in the jieba segmenter; fall back to a copy
    from web.services.documents import ADMIN_LEVEL_PREFIXES  # noqa: E402
except Exception:  # pragma: no cover
    ADMIN_LEVEL_PREFIXES = {
        "central": ["国发", "国办", "国函", "中发", "中办", "发改", "国土资", "建市", "建房",
                    "建科", "人社部", "国税", "财综", "财预", "财建", "环发", "银监",
                    "工信部", "水资源"],
        "provincial": ["粤府", "粤办", "粤财", "粤价", "粤发", "粤卫", "粤环"],
        "municipal": ["深府", "深发", "深办", "深市", "深人", "深规土", "深建", "深前海"],
        "district": ["深坪", "深福", "深南", "深龙", "深宝", "深盐", "深光", "深罗"],
    }

DB_PATH = ROOT / "documents.db"
LOCK_DIR = Path("/tmp/china-governance-daily-sync.lock.d")

LEVELS = ("central", "provincial", "municipal", "district", "department", "media", "research")
LEVEL_RANK = {"central": 0, "provincial": 1, "municipal": 2, "department": 2,
              "district": 3, "media": 4, "research": 4, None: 5, "": 5, "unknown": 5}
NON_ISSUER_SITE_LEVELS = {"media", "research"}
DEPT_SITE_FALLBACK = {"department": "municipal"}
SUBNATIONAL = {"provincial", "municipal", "district", "department"}

# --------------------------------------------------------------------------- #
# A1. level of an agency / locality name                                       #
# --------------------------------------------------------------------------- #
_CENTRAL_NAMES = set(REGISTRY)
_CENTRAL_HEAD = re.compile(r"^(?:中共)?(?:国家|国务院|中共中央|中央|全国|最高人民)")
_LOCALITY_TOKEN = re.compile(r"省|市|自治区|自治州|地区|区|县|分行|分局|特派|驻")
_PROV_MUNI = ("北京市", "上海市", "天津市", "重庆市")
_PROV_HEAD = re.compile(
    r"^(?:中共)?(?:[一-鿿]{2,3}省|[一-鿿]{2,7}自治区|北京市|上海市|天津市|重庆市)")
_PREFECTURE = re.compile(r"自治州|地区|^(?:中共)?[一-鿿]{2,5}盟")
_DISTRICT = re.compile(r"(?<!自治)(?<!地)区(?!域)|县|旗(?=人民|政府|人大|委|$)")  # 旗 = Inner Mongolia banner
_MUNI_HEAD = re.compile(r"^(?:中共)?[一-鿿]{2,4}市")  # 乌鲁木齐市 / 呼伦贝尔市 are 4 chars
_GENERIC_HEAD = re.compile(r"^(?:中共)?(省|市|区|县)")


def level_of_name(name):
    """Administrative level of an issuer / locality name, or None."""
    n = (name or "").strip()
    if not n:
        return None
    if n in _CENTRAL_NAMES:
        return "central"
    if _CENTRAL_HEAD.match(n) and not _LOCALITY_TOKEN.search(
            _CENTRAL_HEAD.sub("", n)):
        return "central"
    if _PREFECTURE.search(n):
        return "municipal"
    if _DISTRICT.search(n):
        return "district"
    if _PROV_HEAD.match(n):
        return "provincial"
    if _MUNI_HEAD.match(n):
        return "municipal"
    m = _GENERIC_HEAD.match(n)
    if m:
        return {"省": "provincial", "市": "municipal", "区": "district", "县": "district"}[m.group(1)]
    return None


# 文号 prefix: the CJK run before the first bracket; drop 依据/依照 metadata leads.
_DOCNUM_PREFIX = re.compile(r"^[一-鿿]{1,12}(?=[〔\[（(【〈《])")
_SUBNAT_PREFIXES = sorted(DOCNUM_SUBNATIONAL, key=len, reverse=True)
_CENTRAL_PREFIXES = sorted(DOCNUM_CENTRAL, key=len, reverse=True)
_WEB_PREFIXES = sorted(((p, lvl) for lvl, ps in ADMIN_LEVEL_PREFIXES.items() for p in ps),
                       key=lambda x: len(x[0]), reverse=True)


def level_of_docnum(docnum, site_level):
    dn = (docnum or "").strip()
    for meta in ("依据", "依照"):
        if dn.startswith(meta):
            dn = dn[len(meta):]
    m = _DOCNUM_PREFIX.match(dn)
    if not m:
        return None
    prefix = m.group(0)
    if prefix.startswith(("公告", "通告", "通知", "令", "第")):
        return None
    for p in _SUBNAT_PREFIXES:
        if prefix.startswith(p):
            return level_of_name(DOCNUM_SUBNATIONAL[p])
    for p, lvl in _WEB_PREFIXES:
        if prefix.startswith(p):
            return lvl
    if site_level == "central":
        for p in _CENTRAL_PREFIXES:
            if prefix.startswith(p):
                return "central"
    return None


_TITLE_HEAD_CUT = re.compile(
    r"(关于|印发|转发|批转|公布|发布|《|丨|\||：|:|对|就|在|向|与|为|组织|开展|召开|举办|举行|"
    r"发出|部署|要求|强调|指出|调研|会见|出席|主持|公告|通告|决定|令$)")
_STATUS_LEAD = re.compile(r"^[（(【\[〔][^）)】\]〕]{1,8}[)）】\]〕]\s*")
_HEAD_SHAPE = re.compile(r"^[一-鿿·、（）()\s]{2,40}$")
# …and it ends like an institution (…办公厅 / …人民政府 / …局) or a bare instrument (…条例)
_HEAD_END = re.compile(
    _INST_SUFFIX + r"$|(?:条例|办法|规定|规则|准则|细则|章程|规程|决定|意见|方案|计划|规划|纲要|措施|法|法典)$")


def level_of_title(title):
    """Level of the issuer named at the HEAD of a title (before the verb frame)."""
    t = _STATUS_LEAD.sub("", clean_title(title))
    m = _TITLE_HEAD_CUT.search(t)
    head = t[: m.start()] if m else t
    head = head.strip(" 　")
    # an issuer head is a contiguous CJK run (no spaces / digits / punctuation):
    # '保障防控前提下租房需求 经纪人进社区 人数次数设限制' is a headline, not a name
    if not head or len(head) > 40 or not _HEAD_SHAPE.match(head) or not _HEAD_END.search(head):
        return None
    if head.startswith("中华人民共和国"):
        return "central"
    return level_of_name(head)


def derive_level(doc, site_level, lead_issuer):
    """-> (admin_level_doc, level_source) per the A1 priority chain."""
    if site_level in NON_ISSUER_SITE_LEVELS:
        return site_level, "site"
    lvl = level_of_name(lead_issuer)
    if lvl:
        return lvl, "issuer"
    lvl = level_of_docnum(doc["docnum"], site_level)
    if lvl:
        return lvl, "docnum"
    if doc["site"] == "npc":
        if doc["cat"] in NPC_NATIONAL_CATEGORIES:
            return "central", "npc_publisher"
        lvl = level_of_name(doc["publisher"])
        if lvl:
            return lvl, "npc_publisher"
    lvl = level_of_title(doc["title"])
    if lvl:
        return lvl, "title_cue"
    # the 13 `department` sites are all Shenzhen MUNICIPAL bureaus (crawlers/gkmlpt.py);
    # a bureau's level is its government's level, so the fallback is municipal.
    return DEPT_SITE_FALLBACK.get(site_level, site_level or "unknown"), "site"


# --------------------------------------------------------------------------- #
# A3. genre                                                                    #
# --------------------------------------------------------------------------- #
EXPLAINER_RE = re.compile(
    r"解读|答记者问|一图读懂|一图看懂|图解|图读|政策问答|问答|答问|解答|划重点|读懂|看懂|权威解|负责人就")
READOUT_RE = re.compile(
    r"会议(?!事|制度|规则|室|费)|召开|讲话|调研|座谈|会见|出席|主持|考察|致辞|发言|强调|指出|研讨|调度|督导|走访|慰问|"
    r"举办|举行|开展|"
    r"开幕|闭幕|签约|揭牌|启动仪式|专题学习|传达学习|集体学习|党组会|常委会会议|电视电话会")
NEWS_RE = re.compile(
    r"新闻|报道|快讯|要闻|动态|发布会|记者|回应|反响|热议|侧记|综述|述评|评论|速递|播报|聚焦|"
    r"观察|盘点|亮点|看点|干货|微视频|视频|海报|漫画|有啥|怎么看|怎么办|→|正式发布|"
    r"[^印]发布$|本[报网站台]讯|电$|\d+月\d+日电")
IMPL_RE = re.compile(
    r"实施方案|实施意见|实施细则|实施办法|实施《[^》]+》(?:的)?(?:办法|细则|规定|条例|决定)|变通规定|"
    r"贯彻落实|贯彻|落实|转发|批转|若干措施|具体措施")
CONSULT_RE = re.compile(r"征求.{0,6}意见|意见征集|意见稿|公开征求")
# issuance frame (2)-(4): 关于…的通知/意见/…, …令; (1) is the matcher's institutional
# 印发/发布/公布《X》 wrapper (a bare 《X》 or a masthead before the verb — '北京发布《X》'
# is a news lead, not a promulgation, exactly as extract_citations treats it).
# 公告/通告 are normative only at the centre (税务总局公告 = tax rulings); a local
# 公告 (查处非法社会组织 / 入库名单) is administrative and stays `other`.
_ISSUANCE_FRAME = re.compile(
    r"关于.{2,80}的(?:通知|意见|决定|办法|规定|细则|方案|计划|规划|"
    r"批复|函|纲要|措施|规则|准则|指引|指南)$|令$|第[\d〇零一二三四五六七八九十百]{1,6}号令")
_CENTRAL_ANNOUNCE = re.compile(r"关于.{2,80}的?(?:公告|通告|公报)$")
_BARE_INSTRUMENT = re.compile(
    r"(?:条例|办法|规定|规则|准则|细则|章程|规程|决定|意见|方案|计划|规划|纲要|措施|指引|指南|标准|法|法典)$")
_FULLTEXT_TAIL = re.compile(r"(?:的)?全文$")
_HEADLINE_PUNCT = re.compile(r"[，,：:！!？?；;]")
PROMUL_GENRES = frozenset({
    "regulation", "law", "decree", "opinion", "action_plan", "policy_issuance",
    "strategy", "plan", "work_plan", "decision", "notice", "subsidy", "standard"})
ADMIN_GENRES = frozenset({"personnel", "procurement", "budget", "publicity", "report"})


def title_core(title):
    """clean_title minus trailing 文号 / date / 已废止 annotations and a 全文 tail,
    keeping 《》 balanced (genre_typer.core_title drops a trailing 》, which would
    defeat the wrapper regexes)."""
    t = clean_title(title)
    for _ in range(4):
        nt = _TRAILING_ANNOT_RE.sub("", t).strip()
        nt = re.sub(r"[\s、，,。.·\-—]+$", "", nt).strip()
        if nt == t or not nt:
            break
        t = nt
    return _FULLTEXT_TAIL.sub("", t)


def _quoted_wrapper(core):
    """-> 'inst' (bare 《X》 or masthead+verb《X》), 'news' (non-masthead lead+verb《X》,
    e.g. 北京发布《X》), or None."""
    m = _WRAP_QUOTED.match(core)
    if not m:
        return None
    pre = m.group("pre").strip()
    if pre == "":
        return "inst"
    if m.group("verb") is None:
        return None  # 贯彻落实《X》 — about X
    return "inst" if _MASTHEAD_PRE.match(pre) else "news"


def _institutional_wrapper(core):
    return _quoted_wrapper(core) == "inst" or bool(_WRAP_PLAIN.match(core))


def is_issuance_frame(core, full, level=None):
    return (_institutional_wrapper(core) or bool(_ISSUANCE_FRAME.search(core)) or (
        level == "central" and bool(_CENTRAL_ANNOUNCE.search(core))) or (
        bool(_BARE_INSTRUMENT.search(core)) and not READOUT_RE.search(full)
        and not core.startswith("关于") and len(core) <= 60
        and not _HEADLINE_PUNCT.search(core)))  # '…发展，安徽出台…实施办法' is a headline


def derive_genre(title, algo_type, level):
    """-> promulgation | implementing | explainer | readout | news | other."""
    full = clean_title(title)
    core = title_core(title)
    if not full:
        return "other"
    if EXPLAINER_RE.search(full):
        return "explainer"
    frame = is_issuance_frame(core, full, level)
    if READOUT_RE.search(full) and not frame:
        return "readout"
    if not frame and (NEWS_RE.search(full) or NONISSUE_RE.search(full)
                      or _quoted_wrapper(core) == "news"):
        return "news"
    if CONSULT_RE.search(full) or algo_type == "consultation":
        return "other"  # a draft out for comment is not (yet) an instrument
    if algo_type in ADMIN_GENRES and not _institutional_wrapper(core):
        return "other"  # 任职的通知 / 中标公告 / 决算: administrative acts, not instruments
    if level in SUBNATIONAL and IMPL_RE.search(core) and (
            frame or algo_type in IMPLEMENTING_GENRES or algo_type == "regulation"):
        return "implementing"
    if frame:
        return "promulgation"
    if level == "media":
        return "news"  # on a media site only an institutional frame is a reprint; the rest is news
    if level == "research":
        return "other"  # reports, translations (chinalawtranslate), institute notices
    if algo_type in PROMUL_GENRES:
        return "promulgation"
    if NEWS_RE.search(full):
        return "news"
    return "other"


# --------------------------------------------------------------------------- #
# A2. instrument key                                                           #
# --------------------------------------------------------------------------- #
KEY_MIN = 6
EDITION_GAP_DAYS = 400
# Pool CLASS: promulgations and the untyped residual may be copies of one text;
# an implementing instrument (转发/实施方案 at a lower level) is a distinct act and
# pools only with its own copies; explainer / readout / news never pool.
POOL_CLASS = {"promulgation": "p", "other": "p", "implementing": "i"}


def _best_core(title):
    """-> (raw core, normalized core) of a stored title (the matcher's exact-core
    tier), or (None, None) when nothing reaches KEY_MIN."""
    title = _FULLTEXT_TAIL.sub("", clean_title(title))
    cores = _title_cores_of_title(title or "")
    best = raw = None
    for core, flag in cores:
        if flag != 1:
            continue  # non-institutional lead ('北京发布《X》') is news ABOUT X
        nc = _norm_title(core)
        if len(nc) < KEY_MIN:
            continue
        # prefer the innermost (shortest) institutional core: the 《X》 over the wrapper
        if best is None or len(nc) < len(best):
            best, raw = nc, core
    if best is None:
        raw = clean_title(title)
        nt = _norm_title(raw)
        if len(nt) >= KEY_MIN:
            best = nt
        else:
            raw = None
    return raw, best


def instrument_key(title):
    """Normalized instrument core of a stored title (the matcher's exact-core tier)."""
    return _best_core(title)[1]


# --- localized re-issuance ---------------------------------------------------
# First locality element of a name: X省 / X自治区 / X市 / X自治州 / X地区 / X盟
# (乌鲁木齐市 is 4 chars; 新疆维吾尔自治区 is 5 + 自治区); optional district element.
_LOC_FIRST = re.compile(
    r"^([一-鿿]{2,3}省|[一-鿿]{2,7}?自治区|[一-鿿]{2,4}?(?:市|自治州|地区|盟))")
_LOC_DISTRICT = re.compile(r"^[一-鿿]{2,4}?(?:新区|区|县|旗)")
_LOC_LEVELS = ("provincial", "municipal", "district")


def _known_localities():
    """Locality names the 文号 registry already vouches for (广东省, 深圳市, 苏州市 …)."""
    out = set(_PROV_MUNI)
    for agency in DOCNUM_SUBNATIONAL.values():
        a = agency[2:] if agency.startswith("中共") else agency
        m = _LOC_FIRST.match(a)
        if m:
            out.add(m.group(1))
    return frozenset(out)


KNOWN_LOCALITIES = _known_localities()


def masthead_of(title):
    """The issuing-body masthead before the 关于/印发 frame of a title ('' if none)."""
    t = _NEWS_LEAD.sub("", _STATUS_TAG.sub("", title_core(title)))
    m = _WRAP_QUOTED.match(t) or _WRAP_PLAIN.match(t)
    if m:
        pre = m.group("pre")
    else:
        i = t.find("关于")
        pre = t[:i] if i > 0 else ""
    pre = pre.strip(" 　丨·、")
    return pre if pre and _MASTHEAD_PRE.match(pre) else ""


def locality_of_head(head):
    """Sub-national locality named by an issuer masthead: '深圳市', '广东省',
    '深圳市龙华区'; '<municipal>' for an unqualified self-reference (市人民政府办公室);
    None for a central or unrecognized head."""
    lvl = level_of_name(head)
    if lvl not in _LOC_LEVELS:
        return None
    h = head[2:] if head.startswith("中共") else head
    m = _LOC_FIRST.match(h)
    loc = m.group(1) if m else ""
    if lvl == "district":
        md = _LOC_DISTRICT.match(h[len(loc):])
        if md:
            loc += md.group(0)
    return loc or f"<{lvl}>"


def locality_in_core(core, masthead_loc):
    """A locality PREFIX inside an instrument core ('深圳市推动…行动方案' -> '深圳市'),
    accepted only when the 文号 registry knows the name, the doc's own masthead names
    it, or it is province-shaped (X省 / X自治区) — '智慧城市建设方案' is not a locality."""
    m = _LOC_FIRST.match(core) or _LOC_DISTRICT.match(core)
    if not m:
        return None
    loc = m.group(0)
    if loc in KNOWN_LOCALITIES:
        return loc
    if masthead_loc and (masthead_loc.startswith(loc) or masthead_loc.endswith(loc)):
        return loc
    if loc.endswith(("省", "自治区")) and _PROV_HEAD.match(loc):
        return loc
    return None


def locality_rank(loc):
    """LEVEL_RANK of a locality string from locality_of_head / locality_in_core."""
    if loc.startswith("<"):
        return LEVEL_RANK[loc.strip("<>")]
    return LEVEL_RANK.get(level_of_name(loc + "人民政府"), 5)


def localize(title, site):
    """-> (stem, locality, locality_rank) for pooling. stem = normalized core minus a
    locality prefix (the text a central instrument and its local re-issuance share);
    locality = the sub-national name the title carries (masthead or core prefix),
    None when the title names none (a bare / central-masthead copy)."""
    raw, key = _best_core(title)
    if key is None:
        return None, None, None
    mast_loc = locality_of_head(masthead_of(title))
    core_loc = locality_in_core(raw, mast_loc if mast_loc and not mast_loc.startswith("<") else "")
    stem = key
    if core_loc:
        s = _norm_title(raw[len(core_loc):])
        if len(s) >= KEY_MIN:
            stem = s
        else:
            core_loc = None
    loc = core_loc or mast_loc
    if core_loc and mast_loc and not mast_loc.startswith("<") and mast_loc.endswith(core_loc):
        loc = mast_loc  # 龙华区X issued by 深圳市龙华区人民政府: the fuller name
    if loc is None:
        return stem, None, None
    if loc.startswith("<"):
        loc = f"{loc}@{site}"  # unqualified 市政府: its own site, never pooled across
        return stem, loc, LEVEL_RANK[loc[1:loc.index(">")]]
    return stem, loc, locality_rank(loc)


# --- jurisdictional chain (for the genre flip) --------------------------------
CITY_PROVINCE_CSV = ROOT / "data" / "city_province.csv"


def load_city_province(path=CITY_PROVINCE_CSV):
    """city -> province for every prefecture-level division (地级市/自治州/地区/盟);
    the four 直辖市 map to themselves (they ARE their province)."""
    import csv
    out = {}
    with open(path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            out[row["city"].strip()] = row["province"].strip()
    return out


CITY_PROVINCE = load_city_province()
# Bare district names the corpus emits WITHOUT a city prefix (Shenzhen district sites
# write 龙华区X / 坪山区X; Wuhan / Nanjing / Qingdao / Chongqing bureaus likewise).
# A '<city><district>' locality (深圳市龙华区, 北京市密云区) is parsed by prefix instead.
DISTRICT_CITY = {
    "福田区": "深圳市", "罗湖区": "深圳市", "南山区": "深圳市", "盐田区": "深圳市",
    "宝安区": "深圳市", "龙岗区": "深圳市", "龙华区": "深圳市", "坪山区": "深圳市",
    "光明区": "深圳市", "光明新区": "深圳市", "大鹏新区": "深圳市", "前海合作区": "深圳市",
    "硚口区": "武汉市", "洪山区": "武汉市", "江汉区": "武汉市", "东湖高新区": "武汉市",
    "江宁区": "南京市", "崂山区": "青岛市", "福山区": "烟台市", "仲恺高新区": "惠州市",
    "龙门县": "惠州市", "周矶管理区": "潜江市", "后湖管理区": "潜江市",
    "重庆高新区": "重庆市", "重庆经开区": "重庆市", "万盛经开区": "重庆市",
}
_BJ_DISTRICTS = ("东城区 西城区 朝阳区 丰台区 石景山区 海淀区 门头沟区 房山区 通州区 顺义区 "
                 "昌平区 大兴区 怀柔区 平谷区 密云区 延庆区 北京经济技术开发区").split()
DISTRICT_CITY.update({d: "北京市" for d in _BJ_DISTRICTS})

# Stems every government writes for ITSELF (self-government housekeeping): a same-stem
# text above the doc is not its parent, so these never flip to `implementing`.
GENERIC_STEM_RE = re.compile(
    r"议事规则|"                                    # 人大常委会/政府 议事规则
    r"制定地方性法规条例|立法条例|"                  # how the local 人大 legislates
    r"讨论.?决定重大事项|"                          # 人大常委会 讨论、决定重大事项的规定
    r"(?:修改|废止)(?:部分|一批|有关)?(?:地方性)?(?:法规|规章|规范性文件|文件|决定)|"  # omnibus amend/repeal decisions
    r"宣布失效|"                                    # 宣布失效一批文件的决定
    r"主要职责内设机构和人员编制|"                   # 三定规定
    r"政府工作规则|"                                # 政府工作规则
    r"(?:政府网站|依法行政|法治政府建设)(?:绩效)?考评|"  # self-assessment schemes
    r"重大行政决策事项目录|"                         # annual decision catalogues
    r"(?:预算|国有资产|规范性文件|计划).{0,4}(?:审查)?监督(?:条例|办法|规定)")  # 人大 oversight regs


def jurisdiction_chain(loc):
    """Ancestor localities of a locality string from localize(): () for a province /
    直辖市 (central is the only superior), ('广东省',) for a city, ('深圳市', '广东省')
    for a district; None when the locality is unknown / unqualified ('<municipal>@sz',
    a false detection such as '转发市')."""
    if not loc or loc.startswith("<"):
        return None
    if loc in _PROV_MUNI or (loc.endswith(("省", "自治区")) and _PROV_HEAD.match(loc)):
        return ()
    if loc in CITY_PROVINCE:
        prov = CITY_PROVINCE[loc]
        return () if prov == loc else (prov,)
    city = DISTRICT_CITY.get(loc)
    if city is None:  # '深圳市龙华区' / '北京市密云区' / '广东省X县': strip the parent prefix
        m = _LOC_FIRST.match(loc)
        if m and len(loc) > len(m.group(1)):
            city = m.group(1)
    if city is None:
        return None
    if city in _PROV_MUNI:
        return (city,)
    prov = CITY_PROVINCE.get(city)
    if prov is None:
        return None if city.endswith("市") else (city,)  # X省X县: province only
    return (city, prov)


def in_chain(m, o):
    """Is higher-ranked same-stem member `o` in doc `m`'s own jurisdictional chain?"""
    if o["level"] == "central":
        return True
    chain = jurisdiction_chain(m["_loc"])
    return bool(chain) and o["_loc"] in chain


_DATE_RE = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})")


def _to_date(s):
    m = _DATE_RE.match(s or "")
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _canon_sort_key(d):
    """promulgation genre > highest doc level > earliest date (the first publication
    is the authoritative copy; reposts come later) > lowest id."""
    return (0 if d["genre"] == "promulgation" else 1, LEVEL_RANK.get(d["level"], 5),
            d["date"] or date.max, d["id"])


def assign_instruments(docs):
    """Set instrument_id / instrument_role on every doc dict (in place)."""
    # Pass 1: group by (class, stem) to find LOCALIZED re-issuances — a doc naming a
    # sub-national locality whose stem also appears on a higher-level member. Those
    # pool under (class, stem, locality); everything else keeps the plain core key.
    stems = defaultdict(list)
    for d in docs.values():
        d["instrument_id"], d["instrument_role"] = d["id"], "unique"
        d["localized"], d["localized_of"], d["_broad_trigger"] = False, None, None
        cls = POOL_CLASS.get(d["genre"])
        if not cls:
            continue
        k = instrument_key(d["title"])
        if not k:
            continue
        stem, loc, rank = localize(d["title"], d["site"])
        d["_key"], d["_stem"], d["_loc"] = k, stem, loc
        d["_rank"] = rank if loc else LEVEL_RANK.get(d["level"], 5)
        stems[(cls, stem)].append(d)
    groups = defaultdict(list)
    n_localized = n_flipped = n_flipped_broad = n_unknown_loc = 0
    for (cls, stem), members in stems.items():
        if len(members) > 1:
            generic = bool(GENERIC_STEM_RE.search(stem))
            for m in members:
                if not m["_loc"]:
                    continue
                higher = [o for o in members if o["_rank"] < m["_rank"] and o["_loc"] != m["_loc"]]
                if not higher:
                    continue
                # pooling isolation: ANY higher same-stem member keeps this doc out of
                # the higher text's pool (a 苏州 条例 must not become a 天津 mirror either)
                m["localized"] = True
                n_localized += 1
                if not (m["genre"] == "promulgation" and m["level"] in SUBNATIONAL):
                    continue
                # genre flip: only an IN-CHAIN parent (qa-genre-flip.md option D + denylist)
                higher.sort(key=lambda o: (o["_rank"], o["date"] or date.max, o["id"]))
                m["_broad_trigger"] = higher[0]["id"]  # what the pre-QA rule would have used
                n_flipped_broad += 1
                if generic:
                    continue
                if jurisdiction_chain(m["_loc"]) is None:
                    n_unknown_loc += 1  # unknown / unqualified locality: cannot place it, no flip
                    continue
                trig = next((o for o in higher if in_chain(m, o)), None)
                if trig is None:
                    continue
                m["genre"] = "implementing"
                m["localized_of"] = trig["id"]
                n_flipped += 1
        for m in members:
            key = (cls, stem, m["_loc"]) if m["localized"] else (cls, m["_key"])
            groups[key].append(m)
    stats = {"n_localized": n_localized, "n_flipped": n_flipped,
             "n_flipped_broad": n_flipped_broad, "n_unknown_loc": n_unknown_loc}
    n_pooled = 0
    for members in groups.values():
        if len(members) < 2 or len({m["site"] for m in members}) < 2:
            continue
        dated = sorted((m for m in members if m["date"]), key=lambda m: m["date"])
        undated = [m for m in members if not m["date"]]
        editions, cur = [], None
        for m in dated:
            if cur is None:
                cur = [m]
                editions.append(cur)
                continue
            gap = (m["date"] - cur[-1]["date"]).days
            if gap > EDITION_GAP_DAYS:
                # a repost carries the TEXT's level (title cue 中华人民共和国… -> central),
                # so test the hosting SITE: only a site at or above the edition's level
                # can open a new edition; a bureau's late copy is a repost.
                canon_rank = min(LEVEL_RANK.get(x["level"], 5) for x in cur)
                if LEVEL_RANK.get(m["site_level"], 5) <= canon_rank:
                    cur = [m]
                    editions.append(cur)
                    continue
            cur.append(m)
        if len(editions) == 1 and undated:
            editions[0].extend(undated)
        for ed in editions:
            if len(ed) < 2 or len({m["site"] for m in ed}) < 2:
                continue
            canon = min(ed, key=_canon_sort_key)
            for m in ed:
                m["instrument_id"] = canon["id"]
                m["instrument_role"] = "canonical" if m is canon else "mirror"
                n_pooled += 1
    stats["n_pooled"] = n_pooled
    return stats


# --------------------------------------------------------------------------- #
# A4. date quality                                                             #
# --------------------------------------------------------------------------- #
STAMP_SHARE = 0.70
STAMP_MIN_DOCS = 100
STAMP_DATE_LO = date(2008, 1, 1)
STAMP_MIN_BULK = 20
# (2026-10-06) The stamp is measured on the site's BULK crawl day, not on the year share.
# The memo rule (>=70% of dated docs in the crawl year) was a proxy for "the crawler wrote
# today's date"; measured against the raw HTML it turned out to flag SHALLOW RECENT crawls
# instead: the Jul-Sep 2026 province/dept/district tier was first crawled ~30 list pages
# deep, so most of its REAL dates fall in 2026 (js_mzt 319/417 equal the page's own
# <meta PubDate>; jcgov/jilin/fujian URL t-dates equal the stored date for 95-100% of docs;
# no crawler in crawlers/ writes today() into date_published). A whole-site "date == crawl
# day" share is fooled the same way — a live site synced daily dates most of its NEW docs on
# their crawl day (liaoning 89%, jcgov 86%, both real). What cannot happen on a real site is
# the first bulk pull of an archive coming back dated on the pull day: that is the stamp. So
# a site is crawl_stamped iff, on its modal crawl day (>= STAMP_MIN_BULK docs), >= 70% of the
# docs are dated on that very day. On the 2026-10-07 corpus this fires on 0 sites (the max is
# leshan, 88% of a 17-doc day, under the floor) — the 74-site / 27.9k-doc exclusion in
# industrial-policy-targeting.md was a coverage-DEPTH artefact, not a date-quality one.


def crawl_stamped_sites(docs, site_level, crawl_year):
    """{site: (n_dated_2008plus, n_on_bulk_day, n_bulk_day_dated_that_day)} for sites whose
    dates are crawl stamps: >=100 dated docs, and >=70% of the docs pulled on the site's
    busiest (modal) crawl day are dated ON that day (an archive pull cannot be)."""
    per_site = defaultdict(lambda: [0, Counter(), Counter()])  # n, crawl-day counts, stamped-per-day
    for d in docs.values():
        if site_level.get(d["site"]) in NON_ISSUER_SITE_LEVELS:
            continue
        dt = d["date"]
        if not dt or dt < STAMP_DATE_LO or dt.year > crawl_year:
            continue
        c = per_site[d["site"]]
        c[0] += 1
        cd = d.get("crawl_date")
        if cd:
            c[1][cd] += 1
            if cd == dt:
                c[2][cd] += 1
    out = {}
    for s, (n, days, eq) in per_site.items():
        if n < STAMP_MIN_DOCS or not days:
            continue
        bulk_day, nb = max(days.items(), key=lambda kv: (kv[1], kv[0]))
        e = eq.get(bulk_day, 0)
        if nb >= STAMP_MIN_BULK and e / nb >= STAMP_SHARE:
            out[s] = (n, nb, e)
    return out


# --------------------------------------------------------------------------- #
# Load + build                                                                 #
# --------------------------------------------------------------------------- #
def connect(db_path, ro=False):
    uri = f"file:{db_path}?mode=ro" if ro else str(db_path)
    conn = sqlite3.connect(uri, uri=ro, timeout=30, isolation_level=None)  # manual txn
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def load(conn):
    site_level = {k: (v or "unknown") for k, v in conn.execute(
        "SELECT site_key, admin_level FROM sites")}
    lead = dict(conn.execute(
        "SELECT doc_id, lead_issuer FROM doc_issuers WHERE lead_issuer IS NOT NULL"))
    docs = {}
    cur = conn.execute(
        """SELECT id, site_key, title, document_number, publisher, date_published,
                  crawl_timestamp, algo_doc_type, classify_main_name
           FROM documents""")
    crawl_years = Counter()
    for (did, sk, title, dn, pub, dp, ct, at, cat) in cur:
        docs[did] = {
            "id": did, "site": sk or "", "title": title or "", "docnum": dn or "",
            "publisher": pub or "", "date": _to_date(dp or ""), "has_date": bool(dp),
            "algo": at or "", "cat": cat or "",
            "crawl_date": _to_date(ct[:10]) if ct else None,
        }
        if ct:
            crawl_years[ct[:4]] += 1
    crawl_year = int(crawl_years.most_common(1)[0][0]) if crawl_years else date.today().year
    return docs, site_level, lead, crawl_year


def build(conn):
    t0 = time.time()
    docs, site_level, lead, crawl_year = load(conn)
    t_load = time.time() - t0
    for d in docs.values():
        sl = site_level.get(d["site"], "unknown")
        li = lead.get(d["id"])
        d["lead_issuer"] = li
        d["level"], d["level_source"] = derive_level(d, sl, li)
        d["genre"] = derive_genre(d["title"], d["algo"], d["level"])
        d["site_level"] = sl
    inst = assign_instruments(docs)
    stamped = crawl_stamped_sites(docs, site_level, crawl_year)
    for d in docs.values():
        if not d["has_date"]:
            d["date_quality"] = "missing"
        elif d["site"] in stamped:
            d["date_quality"] = "crawl_stamped"
        else:
            d["date_quality"] = "good"
    meta = {"t_load": t_load, "t_total": time.time() - t0, "stamped": stamped,
            "crawl_year": crawl_year, **inst}
    return docs, meta


DDL = """
DROP TABLE IF EXISTS doc_identity;
CREATE TABLE doc_identity (
    doc_id INTEGER PRIMARY KEY,
    admin_level_doc TEXT,
    level_source TEXT,
    instrument_id INTEGER,
    instrument_role TEXT,
    genre TEXT,
    date_quality TEXT,
    lead_issuer TEXT,
    localized_of INTEGER
);
CREATE INDEX IF NOT EXISTS idx_doc_identity_level ON doc_identity(admin_level_doc);
CREATE INDEX IF NOT EXISTS idx_doc_identity_instrument ON doc_identity(instrument_id);
CREATE INDEX IF NOT EXISTS idx_doc_identity_genre ON doc_identity(genre);
"""


def write(conn, docs):
    t0 = time.time()
    rows = [(d["id"], d["level"], d["level_source"], d["instrument_id"], d["instrument_role"],
             d["genre"], d["date_quality"], d["lead_issuer"], d["localized_of"])
            for d in docs.values()]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(stmt)
        conn.executemany("INSERT INTO doc_identity VALUES (?,?,?,?,?,?,?,?,?)", rows)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(rows), time.time() - t0


def print_stats(docs, meta, site_level):
    n = len(docs)
    print(f"\ndocs: {n:,}   load {meta['t_load']:.1f}s   compute {meta['t_total']:.1f}s"
          f"   crawl year {meta['crawl_year']}")
    for field in ("level", "level_source", "genre", "instrument_role", "date_quality"):
        c = Counter(d[field] for d in docs.values())
        print(f"\n{field}:")
        for k, v in c.most_common():
            print(f"  {str(k):14s} {v:8,}  {v / n * 100:5.1f}%")
    changed = sum(1 for d in docs.values() if d["level"] != d["site_level"])
    print(f"\nlevel != site level: {changed:,} ({changed / n * 100:.1f}%)")
    xt = Counter((d["site_level"], d["level"]) for d in docs.values() if d["level"] != d["site_level"])
    for (a, b), v in xt.most_common(12):
        print(f"  {a:11s} -> {b:11s} {v:7,}")
    n_inst = len({d["instrument_id"] for d in docs.values()})
    print(f"\ninstruments: {n_inst:,} for {n:,} docs ({meta['n_pooled']:,} docs in pools; "
          f"{meta['n_localized']:,} localized re-issuances kept out of higher-level pools)")
    print(f"genre flips promulgation->implementing: {meta['n_flipped']:,} in-chain "
          f"(broad any-higher rule would flip {meta['n_flipped_broad']:,}; "
          f"{meta['n_unknown_loc']:,} skipped for an unknown locality)")
    print(f"crawl-stamped sites: {len(meta['stamped'])}  "
          f"({sum(1 for d in docs.values() if d['date_quality'] == 'crawl_stamped'):,} docs)")


# --------------------------------------------------------------------------- #
# Validation against known truth                                               #
# --------------------------------------------------------------------------- #
def validate(docs, meta):
    print("\n=== A1 level ===")
    npc = [d for d in docs.values() if d["site"] == "npc"]
    c = Counter(d["level"] for d in npc)
    print(f"npc docs {len(npc):,}: " + ", ".join(f"{k}={v:,}" for k, v in c.most_common()))
    local = [d for d in npc if d["cat"] in ("地方法规", "修改、废止的决定（地方法规）", "法规性决定")]
    cl = Counter(d["level"] for d in local)
    print(f"npc 地方法规/local decisions {len(local):,}: "
          + ", ".join(f"{k}={v:,}" for k, v in cl.most_common()))
    bad = [d for d in local if d["level"] == "central"]
    for d in bad[:5]:
        print(f"   still central: {d['id']} {d['publisher'][:20]!r} {d['title'][:50]}")

    print("\n=== A2 instruments ===")
    xgk = [d for d in docs.values() if _norm_title(clean_title(d["title"])) == "政府信息公开条例"]
    by_inst = defaultdict(list)
    for d in xgk:
        by_inst[d["instrument_id"]].append(d)
    print(f"政府信息公开条例 bare-title copies: {len(xgk)} on {len({d['site'] for d in xgk})} sites "
          f"-> {len(by_inst)} instrument id(s)")
    for iid, ms in sorted(by_inst.items(), key=lambda kv: -len(kv[1])):
        cd = docs[iid]
        dates = sorted(m["date"].isoformat() for m in ms if m["date"])
        print(f"   instrument {iid} (canonical {cd['site']} {cd['level']} {cd['genre']}): "
              f"{len(ms)} copies, {dates[0] if dates else '-'}..{dates[-1] if dates else '-'}")
    for did in (12650974, 12704698, 900105357):
        d = docs.get(did)
        if d:
            print(f"   {did} {d['site']:7s} inst={d['instrument_id']} role={d['instrument_role']:9s} "
                  f"lvl={d['level']} genre={d['genre']} | {d['title'][:48]}")
    ok = (docs[12650974]["instrument_id"] == docs[12704698]["instrument_id"] == 12650974
          and docs[900105357]["instrument_id"] != 12650974) if all(
        k in docs for k in (12650974, 12704698, 900105357)) else None
    print(f"   提振消费 check (gov canonical, xinhua mirror, bj news out): {ok}")
    for did in (900039931, 11271152):
        d = docs.get(did)
        if d:
            print(f"   {did} {d['site']:7s} inst={d['instrument_id']} role={d['instrument_role']:9s} "
                  f"lvl={d['level']} genre={d['genre']} | {d['title'][:48]}")
    ok2 = (docs[11271152]["instrument_id"] != docs[900039931]["instrument_id"]
           and docs[11271152]["genre"] == "implementing") if all(
        k in docs for k in (900039931, 11271152)) else None
    print(f"   以旧换新 check (Shenzhen localized re-issuance is NOT a mirror of the SC text): {ok2}")
    n_inst = len({d["instrument_id"] for d in docs.values()})
    roles = Counter(d["instrument_role"] for d in docs.values())
    print(f"instruments {n_inst:,} vs docs {len(docs):,}; roles {dict(roles)}")

    print("\n=== A3 genre ===")
    print(Counter(d["genre"] for d in docs.values()).most_common())
    hlj = docs.get(12714192)
    if hlj:
        print(f"   黑龙江 AI+ 实施方案 12714192: genre={hlj['genre']} level={hlj['level']}")
    print("   AI+ mention sources (diffusion source_implementing=0):")
    for did in (3507800, 3903923, 3933421, 4771210, 12692769, 12692866, 12758859, 12913722,
                900069411, 900077629, 900082162, 900083978, 900085686, 12715715):
        d = docs.get(did)
        if d:
            print(f"     {did} {d['genre']:12s} {d['level']:10s} | {d['title'][:50]}")

    print("\n=== A4 dates ===")
    st = meta["stamped"]
    print(f"crawl-stamped sites: {len(st)}, docs: "
          f"{sum(1 for d in docs.values() if d['date_quality'] == 'crawl_stamped'):,}")
    for s, (n, nb, e) in sorted(st.items(), key=lambda kv: -kv[1][0])[:12]:
        print(f"   {s:14s} n={n:6,} bulk-day docs={nb:5,} dated-on-bulk-day={e / nb:.2f}")


def dry_run_flips(docs, meta, n=30, seed=7):
    """Broad-rule vs in-chain flip counts and a sample of FLIP-BACKS (docs the pre-QA
    rule flipped to `implementing` that now stay `promulgation`). Read-only."""
    backs = [d for d in docs.values() if d["_broad_trigger"] is not None and d["localized_of"] is None]
    print("\n=== genre flip: broad (any higher same-stem member) vs in-chain + denylist ===")
    print(f"flips before (broad rule): {meta['n_flipped_broad']:,}")
    print(f"flips after  (in-chain):   {meta['n_flipped']:,}")
    print(f"flip-backs:                {len(backs):,}  "
          f"(unknown-locality skips: {meta['n_unknown_loc']:,}; "
          f"generic-stem skips: {sum(1 for d in backs if GENERIC_STEM_RE.search(d['_stem'])):,})")
    lv = Counter(d["level"] for d in backs)
    print("flip-backs by level: " + ", ".join(f"{k}={v:,}" for k, v in lv.most_common()))
    kept = Counter(docs[d["localized_of"]]["level"] for d in docs.values() if d["localized_of"])
    print("kept flips by trigger level: " + ", ".join(f"{k}={v:,}" for k, v in kept.most_common()))
    rnd = random.Random(seed)
    print(f"\n--- {min(n, len(backs))} flip-backs (title | locality | trigger title) ---")
    for d in rnd.sample(backs, min(n, len(backs))):
        t = docs[d["_broad_trigger"]]
        why = "generic" if GENERIC_STEM_RE.search(d["_stem"]) else (
            "unknown-loc" if jurisdiction_chain(d["_loc"]) is None else "out-of-chain")
        print(f"{d['id']:>10} {d['level']:10s} {why:12s} {d['title'][:46]} | {d['_loc']} | "
              f"[{t['level']} {t['_loc'] or '-'} {t['date'] or 'n.d.'}] {t['title'][:46]}")
    for title in ("深圳市人民代表大会常务委员会议事规则", "苏州市客运出租汽车管理条例",
                  "揭阳市人民政府办公室关于印发揭阳市粮食安全责任考核办法的通知",
                  "宁夏回族自治区宗教事务条例"):
        hits = [d for d in docs.values() if clean_title(d["title"]) == title]
        for d in hits[:2]:
            print(f"   sanity {d['id']} genre={d['genre']:12s} localized_of={d['localized_of']} | {title}")


def sample(docs, n, seed, field):
    """Stratified hand-check dump: n docs spread evenly over the field's values."""
    rnd = random.Random(seed)
    by = defaultdict(list)
    for d in docs.values():
        by[d[field]].append(d)
    keys = sorted(by)
    per = max(1, n // len(keys))
    out = []
    for k in keys:
        out.extend(rnd.sample(by[k], min(per, len(by[k]))))
    print(f"\n--- hand-check sample: {len(out)} docs stratified by {field} ---")
    for d in out[:n]:
        print(f"{d['id']:>10} site={d['site']:12s} site_lvl={d['site_level']:10s} "
              f"{field}={d[field]:12s} src={d['level_source']:13s} algo={d['algo']:14s} "
              f"issuer={(d['lead_issuer'] or '-')[:16]:16s} | {d['title'][:70]}")


# --------------------------------------------------------------------------- #
# Self test                                                                    #
# --------------------------------------------------------------------------- #
_LEVEL_TESTS = [
    ("国务院", "central"), ("工业和信息化部", "central"), ("市场监管总局", "central"),
    ("国家税务总局广东省税务局", None),  # vertical bureau in a province: ambiguous, fall through
    ("广东省人民政府", "provincial"), ("江苏省人民代表大会常务委员会", "provincial"),
    ("内蒙古自治区人民代表大会常务委员会", "provincial"), ("上海市人民政府办公厅", "provincial"),
    ("重庆市人民政府", "provincial"), ("广东省工业和信息化厅", "provincial"),
    ("深圳市人民政府", "municipal"), ("深圳市公安局交通警察局", "municipal"),
    ("苏州市人民政府", "municipal"), ("延边朝鲜族自治州人民政府", "municipal"),
    ("深圳市大鹏新区管理委员会", "district"), ("深圳市龙华区人民政府", "district"),
    ("北京经济技术开发区管理委员会", "district"), ("坪山区人民政府", "district"),
    ("市人民政府办公室", "municipal"), ("省政府办公厅", "provincial"), ("区委办", "district"),
    ("中国人民银行广州分行", None),
]
_TITLE_LEVEL_TESTS = [
    ("中华人民共和国政府信息公开条例", "central"),
    ("国务院办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", "central"),
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "central"),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知", "provincial"),
    ("转发省政府办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", None),
    ("深圳市龙华区人民政府办公室关于印发龙华区X办法的通知", "district"),
    ("北京发布《深化改革提振消费专项行动方案》", None),
    ("保障防控前提下租房需求 经纪人进社区 人数次数设限制", None),
    ("江苏省环境保护条例", "provincial"),
]
_GENRE_TESTS = [
    ("中华人民共和国政府信息公开条例", "regulation", "central", "promulgation"),
    ("受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "action_plan", "media", "promulgation"),
    ("北京发布《深化改革提振消费专项行动方案》", "action_plan", "provincial", "news"),
    ("黑龙江省人民政府关于印发《黑龙江省深入实施“人工智能+”行动的实施方案》的通知", "notice", "provincial", "implementing"),
    ("国务院关于深入实施“人工智能+”行动的意见", "opinion", "central", "promulgation"),
    ("【文字解读】《黑龙江省深入实施“人工智能+”行动的实施方案》政策解读", "explainer", "provincial", "explainer"),
    ("保障人民群众依法获取政府信息——政府信息公开条例解读", "explainer", "provincial", "explainer"),
    ("吴泽桐主持召开市政府党组会议 部署人工智能高质量发展工作", "other", "municipal", "readout"),
    ("陈杰吴晓晖到台山市调研督导“百千万工程”推进情况", "other", "municipal", "readout"),
    ("习近平出席2026世界人工智能大会暨人工智能全球治理高级别会议开幕式并发表主旨讲话", "other", "provincial", "readout"),
    ("事关新型政策性金融工具、人工智能发展等，国家发改委最新回应→", "other", "municipal", "news"),
    ("《关于深入实施“人工智能+”行动的意见》引发深圳企业家热烈反响", "other", "municipal", "news"),
    ("转发省政府办公厅关于做好施行《中华人民共和国政府信息公开条例》准备工作的通知", "notice", "municipal", "implementing"),
    ("国务院办公厅转发国家发展改革委关于X实施方案的通知", "notice", "central", "promulgation"),
    ("司法鉴定管理服务项目中标结果公示", "procurement", "municipal", "other"),
    ("2023年深圳市社会保险基金管理局龙岗分局部门决算", "budget", "district", "other"),
    ("关于召开全市安全生产工作会议的通知", "notice", "municipal", "promulgation"),
    ("市委常委会召开会议", "other", "municipal", "readout"),
    ("西藏自治区实施《中华人民共和国草原法》办法", "regulation", "provincial", "implementing"),
    ("新疆维吾尔自治区人民代表大会常务委员会议事规则", "regulation", "provincial", "promulgation"),
    ("积极推进皖港澳法治协同发展，安徽出台律所合伙联营实施办法", "regulation", "media", "news"),
    ("揭阳市人民政府关于庄湃澍等同志任职的通知", "personnel", "municipal", "other"),
    ("Organic Law of the Peoples Courts of the P R C 2018 Revision", "other", "research", "other"),
    ("市北部水源工程管理处举办“一把手”谈安全生产活动", "other", "municipal", "readout"),
    ("国家税务总局关于契税纳税申报有关问题的公告", "application_guide", "central", "promulgation"),
    ("深圳市民政局关于查处非法社会组织的公告", "announcement", "municipal", "other"),
    ("深圳市应急管理局关于向社会公开征求《救灾物资储备标准指引（公开征求意见稿）》意见的通告", "consultation", "municipal", "other"),
]
_KEY_TESTS = [
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》",
     "受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", True),
    ("中华人民共和国政府信息公开条例", "《中华人民共和国政府信息公开条例》全文", True),
    ("中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》",
     "北京发布《深化改革提振消费专项行动方案》", False),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知",
     "广东省推动消费品以旧换新行动方案", True),
]
# localize(title, site) -> (stem, locality): the stem a central text and its local
# re-issuance share, and the sub-national name the title carries (None = bare copy).
_LOCALIZE_TESTS = [
    ("国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知", "gov",
     "推动大规模设备更新和消费品以旧换新行动方案", None),
    ("深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知", "sz",
     "推动大规模设备更新和消费品以旧换新行动方案", "深圳市"),
    ("深圳市人民政府办公厅关于印发深圳市推动大规模设备更新和消费品以旧换新行动方案的通知", "sz",
     "推动大规模设备更新和消费品以旧换新行动方案", "深圳市"),
    ("受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》", "xinhua",
     "提振消费专项行动方案", None),
    ("广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知", "gd",
     "推动消费品以旧换新行动方案", "广东省"),
    ("深圳市龙华区人民政府办公室关于印发龙华区政务公开办法的通知", "lh",
     "政务公开办法", "深圳市龙华区"),
    ("智慧城市建设行动方案", "sz", "智慧城市建设行动方案", None),  # not a locality
    ("市人民政府办公室关于印发市级储备粮管理办法的通知", "huizhou",
     "市级储备粮管理办法", "<municipal>@huizhou"),
]
# assign_instruments on synthetic pools: (docs, {id: (expected instrument_id, role, genre)})
_D = date
_POOL_TESTS = [
    # the live case: Shenzhen's own 以旧换新 plan shares the SC core but is NOT a mirror;
    # the gov + mee copies still pool.
    ([dict(id=900039931, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 13), title="国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知"),
      dict(id=12684861, site="mee", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 18), title="国务院关于印发《推动大规模设备更新和消费品以旧换新行动方案》的通知"),
      dict(id=11271152, site="sz", level="municipal", site_level="municipal", genre="promulgation",
           date=_D(2024, 5, 1), title="深圳市人民政府关于印发推动大规模设备更新和消费品以旧换新行动方案的通知")],
     {900039931: (900039931, "canonical", "promulgation"), 12684861: (900039931, "mirror", "promulgation"),
      11271152: (11271152, "unique", "implementing")}),
    # the xinhua 受权发布 copy is still a mirror of the gov text
    ([dict(id=12650974, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2025, 3, 16), title="中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》"),
      dict(id=12704698, site="xinhua", level="media", site_level="media", genre="promulgation",
           date=_D(2025, 3, 16), title="受权发布丨中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》")],
     {12650974: (12650974, "canonical", "promulgation"), 12704698: (12650974, "mirror", "promulgation")}),
    # a province's localized re-issuance + its bare copy on a dept site form their OWN
    # local pool (canonical = the notice), apart from the central text
    ([dict(id=1, site="gov", level="central", site_level="central", genre="promulgation",
           date=_D(2024, 3, 13), title="国务院关于印发《推动消费品以旧换新行动方案》的通知"),
      dict(id=2, site="gd", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 20), title="广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知"),
      dict(id=3, site="swj", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 25), title="广东省推动消费品以旧换新行动方案")],
     {1: (1, "unique", "promulgation"), 2: (2, "canonical", "implementing"), 3: (2, "mirror", "implementing")}),
    # with NO higher-level text, a local notice and its bare copy pool exactly as before
    ([dict(id=2, site="gd", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 20), title="广东省人民政府关于印发广东省推动消费品以旧换新行动方案的通知"),
      dict(id=3, site="swj", level="provincial", site_level="provincial", genre="promulgation",
           date=_D(2024, 4, 25), title="广东省推动消费品以旧换新行动方案")],
     {2: (2, "canonical", "promulgation"), 3: (2, "mirror", "promulgation")}),
    # --- qa-genre-flip.md cases: the flip needs an IN-CHAIN parent + a non-generic stem ---
    # denylist: every 人大 writes its own 议事规则 — a 福建省 copy is not Shenzhen's parent
    ([dict(id=10, site="npc", level="provincial", site_level="central", genre="promulgation",
           date=_D(2005, 1, 1), title="福建省人民代表大会常务委员会议事规则"),
      dict(id=11, site="sz", level="municipal", site_level="municipal", genre="promulgation",
           date=_D(2019, 1, 1), title="深圳市人民代表大会常务委员会议事规则")],
     {10: (10, "unique", "promulgation"), 11: (11, "unique", "promulgation")}),
    # out of chain: a 贵州省 条例 is not 茂名市's superior -> stays promulgation
    ([dict(id=20, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2017, 1, 1), title="贵州省文明行为促进条例"),
      dict(id=21, site="npc", site_level="central", level="municipal", genre="promulgation",
           date=_D(2022, 1, 1), title="茂名市文明行为促进条例")],
     {20: (20, "unique", "promulgation"), 21: (21, "unique", "promulgation")}),
    # in chain: 广东省 IS 广州市's province -> implementing, localized_of = the GD text
    ([dict(id=30, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2017, 1, 1), title="广东省文明行为促进条例"),
      dict(id=31, site="npc", site_level="central", level="municipal", genre="promulgation",
           date=_D(2022, 1, 1), title="广州市文明行为促进条例")],
     {30: (30, "unique", "promulgation"), 31: (31, "unique", "implementing")}),
    # central in chain for a province: 宁夏 宗教事务条例 under the State Council 条例
    # (memo case 1); 西藏 实施《草原法》办法 is typed implementing by IMPL_RE upstream
    # (see _GENRE_TESTS) and the pool pass leaves it so (no shared stem, no trigger)
    ([dict(id=40, site="gov", site_level="central", level="central", genre="promulgation",
           date=_D(2008, 1, 1), title="宗教事务条例"),
      dict(id=41, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2023, 1, 1), title="宁夏回族自治区宗教事务条例"),
      dict(id=42, site="npc", site_level="central", level="central", genre="promulgation",
           date=_D(2013, 1, 1), title="中华人民共和国草原法"),
      dict(id=43, site="npc", site_level="central", level="provincial",
           genre=derive_genre("西藏自治区实施《中华人民共和国草原法》办法", "regulation", "provincial"),
           date=_D(2020, 1, 1), title="西藏自治区实施《中华人民共和国草原法》办法")],
     {40: (40, "unique", "promulgation"), 41: (41, "unique", "implementing"),
      42: (42, "unique", "promulgation"), 43: (43, "unique", "implementing")}),
    # district: own city is in chain (大鹏新区 <- 深圳市); an unrelated province is not
    ([dict(id=50, site="sz", site_level="municipal", level="municipal", genre="promulgation",
           date=_D(2023, 1, 1), title="深圳市民政局关于进一步规范社会组织举办研讨会论坛活动的通知"),
      dict(id=51, site="dp", site_level="district", level="district", genre="promulgation",
           date=_D(2023, 3, 1), title="大鹏新区统战和社会建设局关于进一步规范社会组织举办研讨会论坛活动的通知"),
      dict(id=52, site="npc", site_level="central", level="provincial", genre="promulgation",
           date=_D(2025, 1, 1), title="湖南省建设工程造价管理办法"),
      dict(id=53, site="lh", site_level="district", level="district", genre="promulgation",
           date=_D(2023, 1, 1), title="深圳市罗湖区人民政府办公室关于印发《罗湖区建设工程造价管理办法》的通知")],
     {50: (50, "unique", "promulgation"), 51: (51, "unique", "implementing"),
      52: (52, "unique", "promulgation"), 53: (53, "unique", "promulgation")}),
]
# localized_of expectations, one dict per _POOL_TESTS entry (id -> trigger id; unlisted = NULL).
# In test 3 the bare GD copy (id 3) is also a provincial-level localization of the SC text.
_LOCALIZED_OF = [{11271152: 900039931}, {}, {2: 1, 3: 1}, {}, {}, {}, {31: 30}, {41: 40}, {51: 50}]
_CHAIN_TESTS = [
    ("广东省", ()), ("北京市", ()), ("宁夏回族自治区", ()), ("广州市", ("广东省",)),
    ("苏州市", ("江苏省",)), ("深圳市龙华区", ("深圳市", "广东省")), ("大鹏新区", ("深圳市", "广东省")),
    ("北京市密云区", ("北京市",)), ("硚口区", ("武汉市", "湖北省")), ("转发市", None),
    ("<municipal>@huizhou", None), (None, None), ("延边朝鲜族自治州", ("吉林省",)),
]
_GENERIC_STEM_TESTS = [
    ("人民代表大会常务委员会议事规则", True), ("制定地方性法规条例", True),
    ("人民代表大会常务委员会讨论决定重大事项的规定", True), ("人民政府关于修改部分规章的决定", True),
    ("人民政府关于宣布失效一批市政府文件的决定", True), ("食品药品监督管理局主要职责内设机构和人员编制规定", True),
    ("人民政府工作规则", True), ("人民政府2022年度重大行政决策事项目录", True),
    ("文明行为促进条例", False), ("粮食安全责任考核办法", False), ("养犬管理条例", False),
    ("推动大规模设备更新和消费品以旧换新行动方案", False),
]


def _stamp_docs(bulk, bulk_stamped, daily, daily_same_day=True, bulk_day=date(2026, 8, 13)):
    """Site 's': `bulk` docs crawled on `bulk_day`, of which `bulk_stamped` are dated ON that
    day and the rest carry a spread of older real dates; then `daily` docs crawled one per
    following day, dated on their crawl day (a live site synced daily) or a day earlier."""
    from datetime import timedelta
    out, i = {}, 0
    for j in range(bulk):
        dt = bulk_day if j < bulk_stamped else date(2024, 1, 1) + timedelta(days=j % 700)
        out[i] = {"site": "s", "date": dt, "crawl_date": bulk_day}; i += 1
    for j in range(daily):
        cd = bulk_day + timedelta(days=1 + j)
        out[i] = {"site": "s", "date": cd if daily_same_day else cd - timedelta(days=1), "crawl_date": cd}; i += 1
    return out


_STAMP_TESTS = [
    # (label, docs, expected stamped set)
    ("bulk stamp: 150-doc pull all dated on the pull day", _stamp_docs(150, 150, 0), {"s"}),
    ("bulk stamp + daily tail (stamped site kept syncing)", _stamp_docs(150, 140, 60), {"s"}),
    ("shallow recent crawl: 200-doc bulk with real dates, 100 daily same-day (jcgov shape)",
     _stamp_docs(200, 10, 100), set()),
    ("js_mzt shape: 200-doc bulk real dates, 217 daily picked up a day late", _stamp_docs(200, 0, 217, False), set()),
    ("whole-site 'in crawl year' 100% but bulk is real (liaoning shape: 62 bulk, 1,100 daily)",
     _stamp_docs(62, 4, 300), set()),
    ("too small (<100 docs)", _stamp_docs(80, 80, 0), set()),
    ("bulk day under the 20-doc floor (leshan shape: 17-doc day, 88% stamped)", _stamp_docs(17, 15, 150), set()),
    ("borderline: exactly 70% of a 20-doc bulk day", _stamp_docs(20, 14, 100), {"s"}),
    ("just under: 69% of a 100-doc bulk day", _stamp_docs(100, 69, 0), set()),
]


def self_test():
    fails = 0
    for name, exp in _LEVEL_TESTS:
        got = level_of_name(name)
        if got != exp:
            fails += 1
            print(f"XX level_of_name({name!r}) = {got!r}, expected {exp!r}")
    for title, exp in _TITLE_LEVEL_TESTS:
        got = level_of_title(title)
        if got != exp:
            fails += 1
            print(f"XX level_of_title({title[:40]!r}) = {got!r}, expected {exp!r}")
    for title, algo, lvl, exp in _GENRE_TESTS:
        got = derive_genre(title, algo, lvl)
        if got != exp:
            fails += 1
            print(f"XX derive_genre({title[:40]!r}, {algo}, {lvl}) = {got!r}, expected {exp!r}")
    for a, b, same in _KEY_TESTS:
        ka, kb = instrument_key(a), instrument_key(b)
        if (ka == kb) != same:
            fails += 1
            print(f"XX instrument_key: {ka!r} vs {kb!r} (expected same={same})")
    for title, site, exp_stem, exp_loc in _LOCALIZE_TESTS:
        stem, loc, _ = localize(title, site)
        if (stem, loc) != (exp_stem, exp_loc):
            fails += 1
            print(f"XX localize({title[:40]!r}) = {(stem, loc)!r}, expected {(exp_stem, exp_loc)!r}")
    for (members, expected), exp_trig in zip(_POOL_TESTS, _LOCALIZED_OF):
        docs = {m["id"]: dict(m) for m in members}
        assign_instruments(docs)
        got = {i: (d["instrument_id"], d["instrument_role"], d["genre"]) for i, d in docs.items()}
        if got != expected:
            fails += 1
            print(f"XX assign_instruments: {got!r}\n   expected {expected!r}")
        lo = {i: d["localized_of"] for i, d in docs.items()}
        exp_lo = {i: exp_trig.get(i) for i in docs}
        if lo != exp_lo:
            fails += 1
            print(f"XX localized_of: {lo!r}\n   expected {exp_lo!r}")
    for loc, exp in _CHAIN_TESTS:
        got = jurisdiction_chain(loc)
        if got != exp:
            fails += 1
            print(f"XX jurisdiction_chain({loc!r}) = {got!r}, expected {exp!r}")
    for stem, exp in _GENERIC_STEM_TESTS:
        if bool(GENERIC_STEM_RE.search(stem)) != exp:
            fails += 1
            print(f"XX GENERIC_STEM_RE({stem!r}) expected {exp}")
    for label, docs, exp in _STAMP_TESTS:
        got = set(crawl_stamped_sites(docs, {"s": "municipal"}, 2026))
        if got != exp:
            fails += 1
            print(f"XX crawl_stamped_sites[{label}] = {got!r}, expected {exp!r}")
    total = (len(_LEVEL_TESTS) + len(_TITLE_LEVEL_TESTS) + len(_GENRE_TESTS) + len(_KEY_TESTS)
             + len(_LOCALIZE_TESTS) + len(_POOL_TESTS) + len(_CHAIN_TESTS) + len(_GENERIC_STEM_TESTS)
             + len(_STAMP_TESTS))
    print(f"self-test: {total - fails}/{total} passed")
    return fails == 0


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="compute + stats, no write")
    ap.add_argument("--dry-run-flips", action="store_true",
                    help="broad vs in-chain genre-flip counts + 30 sample flip-backs; read-only, no write")
    ap.add_argument("--validate", action="store_true", help="run the A1–A4 truth checks")
    ap.add_argument("--sample", type=int, default=0, help="stratified hand-check dump of N docs")
    ap.add_argument("--sample-field", default="level", choices=["level", "genre"])
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--force", action="store_true", help="write even if the nightly lock exists")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1

    writing = not (args.dry_run or args.dry_run_flips or args.validate or args.sample)
    if writing and LOCK_DIR.exists() and not args.force:
        print(f"nightly lock {LOCK_DIR} exists — refusing to write (use --force)")
        return 2

    conn = connect(args.db, ro=not writing)
    docs, meta = build(conn)
    site_level = {d["site"]: d["site_level"] for d in docs.values()}
    print_stats(docs, meta, site_level)
    if args.validate:
        validate(docs, meta)
    if args.dry_run_flips:
        dry_run_flips(docs, meta, seed=args.seed)
    if args.sample:
        sample(docs, args.sample, args.seed, args.sample_field)
    if writing:
        n, t = write(conn, docs)
        print(f"\nwrote doc_identity: {n:,} rows in {t:.1f}s (one transaction)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
