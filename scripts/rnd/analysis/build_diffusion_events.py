"""Diffusion-events auto-matcher — step 1 of the daily policy tracker.

Builds the `diffusion_events` table IN `documents.db`: for each sub-national
document, the central instrument it implements and the lag between them. Turns the
hand-built cascade tables in `docs/research/consumption-diffusion.md` and
`ai-governance-diffusion.md` into a self-updating feed.

Concept: `docs/research/daily-tracker-concept.md` (piece 3, "auto-matching").

Three match signals, strongest first (de-duplicated per (source, anchor) pair):
  citation      — a resolved `citations` edge (or an exact 《》-core ref) from a
                  sub-national doc to an anchor member. Direct.
  title_reissue — the sub-national title carries the anchor's distinctive named
                  stem (《》-core, genre-suffix stripped) or a quoted "X+" cue.
                  Catches localized re-issuances citations miss.
  topic_genre   — same topics_algo tag, sub-national implementing genre, within a
                  window after a central framework instrument, no stronger match.
                  Lower confidence (probable-but-unconfirmed implementation).

Reuses `TitleMatcher` + the `_norm_title` normalization from
`scripts/rnd/citations/extract_citations.py` (no new fuzzy matcher).

    python3 scripts/rnd/analysis/build_diffusion_events.py            # dry run (read-only)
    python3 scripts/rnd/analysis/build_diffusion_events.py --write    # build the table
    python3 scripts/rnd/analysis/build_diffusion_events.py --validate # + print validation

DOCUMENT IDENTITY comes from the `doc_identity` side table (scripts/build_doc_identity.py,
corpus-lessons.md A1–A5), rebuilt nightly just before this script. The matcher no
longer derives any of it:
  * level     = `admin_level_doc` (the ISSUER's level, per document — a State Council
                text reposted on a bureau site is central; an npc 地方法规 is provincial).
                Anchors: central / provincial. Sources: provincial/municipal/district
                (/department) for central anchors, sub-provincial for provincial ones.
  * pooling   = `instrument_id`: all mirrors of one text (Xinhua 受权发布, list-chrome
                copies, departmental reposts) share one id; the `canonical` member is
                the anchor representative and the mirrors inherit the anchor, so a
                citation the resolver sent to a mirror still reaches the anchor.
  * genre     = `genre` (promulgation|implementing|explainer|readout|news|other):
                explainer/readout/news members never qualify a pool as an anchor, and
                `source_implementing` = 1 iff the source genre is promulgation or
                implementing (title_reissue rows are implementing by construction).
`algo_doc_type` is still read for the FRAMEWORK test (regulation/opinion/action_plan/…
+ title cues) and the CAMPAIGN gate of topic_genre — those are instrument-kind
labels, not identity.

Second anchor class — PROVINCIAL framework instruments (2026-10, fidelity-provincial.md):
in 92.8% of full center→province→city chains the city's text descends from the
PROVINCE (cities relay their province 10.8% vs provinces relaying the center 3.3%),
so the province→city hop is the one that carries policy text. `anchor_level`
('central' | 'provincial') marks which class a row belongs to. Provincial anchors
are province-level instruments (admin_level_doc='provincial' — which already folds
the Chongqing portal and Beijing/Shanghai bureaus to their government's level),
pooled by instrument_id and split per province, skipping pools already anchored
centrally (a provincial mirror of a central text is the central cascade, not a
provincial one). They match ONLY sub-provincial implementers in the SAME province
(`province_of`, a site→province map); the memo's cross-province edges were
resolver noise. Same three match types and lag rules.

Bare 五年规划 period mentions are never attributed (`GENERIC_FYP_RE`, atlas §7).
Every event stays in the table — the mention signal is still informative — the
rollup and /tracker just count implementing-only by default and show mentions as a
secondary number.
"""
import argparse
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve()
ROOT = _HERE.parents[3]
DEFAULT_DB = ROOT / "documents.db"
# Reuse the citation resolver's matcher + normalization (do NOT reinvent).
sys.path.insert(0, str(_HERE.parents[1] / "citations"))
sys.path.insert(0, str(_HERE.parent))
from extract_citations import TitleMatcher, _norm_title, _INNER_TITLE  # noqa: E402
from geo import province_code_of_site_name, PROVINCE_CODE  # noqa: E402

DATE_LO, DATE_HI = "2000-01-01", "2026-12-31"
MAX_LAG = 1500  # days; cap positive lags (0..~4yr)

# Framework genres (algo_doc_type) that make a central doc an "instrument".
FW_GENRES = {"regulation", "opinion", "action_plan", "strategy", "plan",
             "law", "decree", "decision", "work_plan"}
# The subset that genuinely *diffuses* (used to gate topic_genre anchors).
CAMPAIGN_GENRES = {"opinion", "action_plan", "strategy", "plan"}
# Title cues that also mark a framework instrument (genre tagger misses some).
FW_TITLE_RE = re.compile(r"(意见|规定|办法|规划|行动方案|实施方案|条例|纲要|决定|细则)")

# Authority: a central framework doc is an anchor if it clears this OR is a named
# (《》-core) instrument (the named branch keeps brand-new flagships the citation
# graph has not yet absorbed — e.g. 提振消费专项行动方案, cr/indeg still 0).
CR_T, DEG_T = 5.0, 3

# Genre suffixes stripped off a 《》-core to get the distinctive topic stem, longest
# first; stripping stops before the stem would fall below STEM_MIN chars.
GENRE_SUFFIXES = sorted(
    ["实施方案", "行动方案", "行动计划", "工作方案", "实施意见", "实施办法",
     "若干措施", "实施细则", "专项行动", "管理办法", "管理规定",
     "行动", "方案", "计划", "意见", "办法", "规定", "通知", "规划",
     "条例", "决定", "细则", "措施", "专项", "纲要", "规则"],
    key=len, reverse=True)
STEM_MIN = 6

# Candidate (sub-national) filters for title_reissue / topic_genre.
SUBNATIONAL = {"provincial", "municipal", "district", "department"}
SUBPROVINCIAL = {"municipal", "district", "department"}
ISSUANCE_RE = re.compile(r"(印发|发布|的通知|的决定|的意见|行动方案|实施方案|"
                         r"行动计划|实施意见|若干措施|工作方案|办法|规定)")
# Explainers, readouts, meeting notices, scraped list-chrome — NOT re-issuances.
# (Title-shape gate for title_reissue CANDIDATES; also the ancestor of
# build_doc_identity's readout/news genre rule, which imports it.)
NONISSUE_RE = re.compile(r"(解读|读懂|答记者问|新闻发布|发布会|新华鲜报|点击数|"
                         r"标题[:：]|主持|讲话|调研|座谈|电视电话会议|常务会议|"
                         r"党组会议|常委会|访谈|专家|引发|热议|侧记|综述)")
# Quoted "X+" cue inside “”/‘’/「」/《》 (highly distinctive, e.g. 人工智能+, 互联网+).
CUE_QUOTE_RE = re.compile(r"[“‘「『《]([^”’」』》]{2,20}\+[^”’」』》]{0,20})[”’」』》]")

# --- doc_identity genres -----------------------------------------------------
# A doc ABOUT an instrument (解读 / 党组会议 readout / 新闻) may stay a pool member
# (so citations mis-resolved onto it still reach the pool) but can neither
# represent nor qualify a pool as an anchor (atlas §7).
ABOUT_GENRES = {"explainer", "readout", "news"}
# A source whose own text is a policy instrument → the event is an implementation,
# not a mention (diffusion-fidelity.md "implementing-instrument subset").
IMPLEMENTING_IDENTITY_GENRES = {"promulgation", "implementing"}

TOPIC_WINDOW = 365  # days: topic_genre recency gate
TOPIC_ANCHOR_CR = 10.0  # only major campaigns propose topic_genre implementations

# Bare five-year-plan mentions ("十五五"规划, 十四五规划纲要) name a planning period,
# not an instrument; the resolver nonetheless pins them to whichever sectoral
# 十X五 plan it finds first (atlas §7: a 十五五 电子信息 plan 解读 with 303 such
# edges was the one pure resolver-noise anchor). Never attribute these by target_id.
GENERIC_FYP_RE = re.compile(r"^十[一二三四五六]五(规划|规划纲要|计划)?$")


# --- Provincial anchors: province map + helpers ------------------------------
# site_key -> province code. TWO layers (a SITE attribute — where a doc was crawled —
# not document identity):
#   1. OVERRIDE: the hand table below (_PROV_EXACT exact keys, then _PROV_PREFIX
#      prefixes) — for site keys whose display name is opaque (gz, sz_invest, bjb_*)
#      or where a prefix rule is cheaper than 20 rows (szd_, bjd_, xz_).
#   2. FALLBACK (geo.py): derive the province from the site's display name in
#      `sites.name` (晋城市 -> 山西省 -> sx; "Wuhan Qiaokou District (武汉硚口区)" ->
#      武汉市 -> hb) via data/city_province.csv + DISTRICT_CITY + the English alias
#      table. Added 2026-10 when 42 of the municipal/district sites (7.8k docs) had
#      silently rotted out of the hand table (jcgov, wuhan, suzhou_ah, leshan, …),
#      so their docs never joined a provincial chain. New sites now resolve as long
#      as their name carries the city; a site that resolves to None is counted and
#      printed once at build time (`_report_unresolved`).
# Codes: see geo.PROVINCE_CODE (existing codes kept verbatim; the rest ISO 3166-2:CN).
_PROV_EXACT = {
    # Guangdong: portal + depts, Guangzhou, Shenzhen portals/bureaus/districts, gkmlpt cities
    "gz": "gd", "sz": "gd", "sz_invest": "gd",
    "heyuan": "gd", "huizhou": "gd", "jiangmen": "gd", "jieyang": "gd", "maoming": "gd",
    "shantou": "gd", "shanwei": "gd", "shaoguan": "gd", "yangjiang": "gd", "yunfu": "gd",
    "zhanjiang": "gd", "zhaoqing": "gd", "zhongshan": "gd", "zhuhai": "gd",
    "audit": "gd", "fgw": "gd", "ga": "gd", "hrss": "gd", "jtys": "gd", "mzj": "gd",
    "sf": "gd", "stic": "gd", "swj": "gd", "szeb": "gd", "wjw": "gd", "yjgl": "gd", "zjj": "gd",
    # Jiangsu
    "suzhou": "js", "nanjing": "js", "changzhou": "js", "huaian": "js", "lyg": "js", "nantong": "js",
    "taizhou_js": "js", "wuxi": "js", "yancheng": "js",
    # Beijing / Shanghai / Chongqing (province-tier municipalities)
    "bj": "bj", "sh": "sh", "cq": "cq",
    # `sites.name` says "Qianjiang (潜江市)" (Hubei) but www.qianjiang.gov.cn is 重庆市黔江区
    # (its docs carry 黔江府发 文号; Hubei 潜江 is `hbqj`) — found 2026-10-07 by the
    # doc_identity.province audit, 28/40 docs name 黔江. Override beats the name.
    "qianjiang": "cq",
    # Fujian
    "fujian": "fj", "fuzhou_fj": "fj", "longyan": "fj", "quanzhou": "fj", "sm": "fj",
    # Hunan
    "hunan": "hn", "changde": "hn", "huaihua": "hn", "yueyang": "hn",
    # Jilin
    "jilin": "jl", "changchun": "jl", "liaoyuan": "jl", "siping": "jl", "tonghua": "jl",
    "yanbian": "jl",
    # Liaoning
    "liaoning": "ln", "chaoyang": "ln", "dandong": "ln", "fushun": "ln", "fuxin": "ln",
    "panjin": "ln", "shenyang": "ln", "yingkou": "ln",
    # Ningxia
    "ningxia": "nx", "shizuishan": "nx", "wuzhong": "nx", "yinchuan": "nx",
    # Shandong
    "shandong": "sd", "heze": "sd", "jinan": "sd", "jining": "sd", "laiwu": "sd",
    "liaocheng": "sd", "linyi": "sd", "qingdao": "sd", "taian": "sd", "weihai": "sd",
    "yantai": "sd", "zibo": "sd",
    # Tibet
    "xizang": "xz", "al": "xz", "changdu": "xz", "lasa": "xz", "linzhi": "xz",
    "naqu": "xz", "shannan": "xz",
    # Zhejiang / Heilongjiang / Qinghai / Xinjiang
    "zj": "zj", "hangzhou": "zj",
    "hlj": "hlj", "dxal": "hlj", "hegang": "hlj", "heihe": "hlj", "jixi": "hlj",
    "shuangyashan": "hlj", "suihua": "hlj", "yc": "hlj",
    "qinghai": "qh", "hainanzhou": "qh", "yushu": "qh",
    "xinjiang": "xj", "ale": "xj", "bts": "xj", "cj": "xj", "hami": "xj", "kashi": "xj",
    "klmy": "xj", "nqs": "xj", "tlf": "xj", "wjq": "xj", "wlmq": "xj", "xjboz": "xj",
    "xjbz": "xj", "xjht": "xj", "xjkz": "xj", "xjtc": "xj", "xjyl": "xj",
}
_PROV_PREFIX = [
    ("szd_", "js"),                        # Suzhou districts/county cities, BEFORE the sz* rule
    ("gd", "gd"), ("sz", "gd"),            # gd*, sz* (Shenzhen districts)
    ("js_", "js"), ("js", "js"), ("njd_", "js"),
    ("bjb_", "bj"), ("bjd_", "bj"), ("shb_", "sh"),
    ("cq_", "cq"), ("cqd_", "cq"), ("fj_", "fj"), ("hn_", "hn"), ("jl_", "jl"),
    ("ln_", "ln"), ("nx_", "nx"), ("sd_", "sd"), ("xz_", "xz"),
]
# Leading place name stripped off a provincial core before stemming, so the stem
# is the topic (推动消费品以旧换新) that a city re-issuance (惠州市推动消费品以旧换新行动方案)
# carries. 8-char floor (memo §1).
PLACE_RE = re.compile(r"^[一-鿿]{2,4}(省|市|自治区|回族自治区|维吾尔自治区|壮族自治区)")
# "…关于印发X的通知" without 《》 (many provincial portals omit the brackets).
ISSUE_CORE_RE = re.compile(r"印发(.{8,}?)的通知")
PROV_STEM_MIN = 8


_SITE_NAMES = {}  # site_key -> sites.name; filled by load_site_names() before load()


def load_site_names(conn):
    """Read `sites` (key -> display name) for the province_of fallback."""
    _SITE_NAMES.clear()
    _SITE_NAMES.update(conn.execute("SELECT site_key, name FROM sites"))
    return _SITE_NAMES


def province_of_override(site):
    """Layer 1 only: the hand table (exact keys, then prefixes). None if absent."""
    p = _PROV_EXACT.get(site)
    if p:
        return p
    for pref, code in _PROV_PREFIX:
        if site.startswith(pref):
            return code
    return None


def province_of(site, site_name=None):
    """Province code of a site: hand-table override, else derived from the site's
    display name (`site_name`, default: the `sites` table loaded by load_site_names).
    None when neither layer knows the site."""
    p = province_of_override(site)
    if p:
        return p
    return province_code_of_site_name(site_name if site_name is not None else _SITE_NAMES.get(site))


def _report_unresolved(docs):
    """Count and print ONCE the sub-national sites (with docs in the window) that
    province_of cannot place — these docs never join a provincial chain."""
    per_site = Counter(d["site"] for d in docs.values()
                       if d["level"] in SUBNATIONAL and not d["prov"])
    if per_site:
        n_docs = sum(per_site.values())
        shown = ", ".join(f"{s}({n})" for s, n in per_site.most_common(12))
        more = f", +{len(per_site) - 12} more" if len(per_site) > 12 else ""
        print(f"  province_of: {len(per_site)} sub-national sites / {n_docs} docs unresolved "
              f"(no provincial chain): {shown}{more}")
    return per_site


def prov_core(title):
    """Instrument core of a provincial title: the 《》 inner, else the 印发X的通知 X."""
    c = inner_core(title)
    if c:
        return c
    m = ISSUE_CORE_RE.search(title or "")
    return m.group(1) if m else None


def _d10(s):
    return (s or "")[:10]


def _lag(src_date, anchor_date):
    try:
        y1, m1, d1 = map(int, src_date.split("-"))
        y2, m2, d2 = map(int, anchor_date.split("-"))
        return (date(y1, m1, d1) - date(y2, m2, d2)).days
    except (ValueError, AttributeError):
        return None


def inner_core(title):
    """First 《...》 inner title (>=8 chars), else None."""
    m = _INNER_TITLE.search(title or "")
    return m.group(1) if m else None


def named_cores(members):
    """Normalized 《》-cores (>= STEM_MIN chars) carried by a pool's member titles.
    Non-empty = the pool is a NAMED instrument (authority not required)."""
    cores = set()
    for m in members:
        c = inner_core(m["title"])
        if c:
            nc = _norm_title(c)
            if len(nc) >= STEM_MIN:
                cores.add(nc)
    return cores


def genre_stem(norm_core):
    """Strip trailing genre suffixes off a normalized core to the topic stem,
    never dropping below STEM_MIN chars. 提振消费专项行动方案 -> 提振消费专项;
    推动大规模设备更新和消费品以旧换新行动方案 -> 推动大规模设备更新和消费品以旧换新."""
    s = norm_core
    changed = True
    while changed:
        changed = False
        for suf in GENRE_SUFFIXES:
            if s.endswith(suf) and len(s) - len(suf) >= STEM_MIN:
                s = s[:-len(suf)]
                changed = True
                break
    return s


def is_framework(genre, title):
    return genre in FW_GENRES or bool(FW_TITLE_RE.search(title or ""))


def can_anchor(d):
    """May this doc represent / qualify an anchor pool: a framework instrument that
    is not merely ABOUT one (explainer / readout / news per doc_identity)."""
    return is_framework(d["genre"], d["title"]) and d["igenre"] not in ABOUT_GENRES


def is_implementing(source, match_type):
    """0/1: is this (source doc, match_type) an implementing event rather than a
    mention? `source` is a docs-dict entry (key: igenre = doc_identity.genre).
    title_reissue is implementing by construction (the title IS a re-issuance)."""
    if match_type == "title_reissue":
        return 1
    return 1 if source["igenre"] in IMPLEMENTING_IDENTITY_GENRES else 0


# --------------------------------------------------------------------------- #
# Load corpus                                                                  #
# --------------------------------------------------------------------------- #
def load(conn):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='doc_identity'"
                        ).fetchone():
        sys.exit("ERROR: doc_identity table missing — run scripts/build_doc_identity.py first")
    indeg = Counter()
    for tid, n in conn.execute(
            "SELECT target_id, COUNT(*) FROM citations WHERE target_id IS NOT NULL GROUP BY target_id"):
        indeg[tid] = n
    docs = {}
    n_noid = 0
    for row in conn.execute(
            f"""SELECT d.id, d.site_key, d.title, d.date_published, d.algo_doc_type,
                       d.citation_rank, d.topics_algo,
                       i.admin_level_doc, i.instrument_id, i.genre, i.province
                FROM documents d LEFT JOIN doc_identity i ON i.doc_id = d.id
                WHERE d.date_published BETWEEN '{DATE_LO}' AND '{DATE_HI}'"""):
        did, sk, title, dp, genre, cr, topics, lvl, iid, igenre, iprov = row
        if lvl is None:
            n_noid += 1  # crawled after the identity build: no level → never anchor/source
        docs[did] = {
            "id": did, "site": sk, "title": title or "",
            "date": _d10(dp), "genre": genre or "", "cr": cr or 0.0,
            "topics": [t for t in (topics or "").split(",") if t],
            "level": lvl or "unknown",
            "inst": iid if iid is not None else did,
            "igenre": igenre or "",
            "indeg": indeg.get(did, 0),
            "ntitle": _norm_title(title or ""),
            # per-DOCUMENT province (doc_identity A6: the issuing locality, so npc 地方法规
            # and 省通信管理局 docs on national sites join their province), else the site's
            "prov": iprov or province_of(sk),
        }
    if n_noid:
        print(f"  ({n_noid} docs have no doc_identity row — excluded as anchors/sources)")
    return docs


# --------------------------------------------------------------------------- #
# Build anchors (central framework instruments, pooled by instrument_id)       #
# --------------------------------------------------------------------------- #
def _anchor_record(rep, members, base, prov=None):
    stem = genre_stem(base) if base else ""
    cues = [_norm_title(c) for c in CUE_QUOTE_RE.findall(rep["title"])]
    rec = {
        "id": rep["id"], "date": rep["date"], "title": rep["title"],
        "ntitle": rep["ntitle"], "genre": rep["genre"], "cr": rep["cr"],
        "topics": rep["topics"], "stem": stem if len(stem) >= STEM_MIN else None,
        "cues": [c for c in cues if "+" in c],
        "members": [m["id"] for m in members],
    }
    if prov is not None:
        rec["prov"] = prov
    return rec


def build_anchors(docs):
    pools = defaultdict(list)
    for d in docs.values():
        pools[d["inst"]].append(d)

    anchors = {}            # anchor_id (canonical doc) -> anchor dict
    member_to_anchor = {}   # any member doc id -> anchor_id
    core_exact = {}         # normalized 《》-core -> anchor_id (for ref attribution)

    n_rep_ineligible = n_rep_unloaded = 0
    for iid, members in pools.items():
        rep = docs.get(iid)
        if rep is None:
            # canonical outside the date window (undated / pre-2000); its dated
            # mirrors cannot stand in for it
            if any(m["level"] == "central" and can_anchor(m) for m in members):
                n_rep_unloaded += 1
            continue
        if not (rep["level"] == "central" and can_anchor(rep)):
            if any(m["level"] == "central" and can_anchor(m) for m in members):
                n_rep_ineligible += 1
            continue
        cores = named_cores(members)
        has_auth = any(m["cr"] >= CR_T or m["indeg"] >= DEG_T for m in members)
        if not (cores or has_auth):
            continue
        if not rep["date"]:
            continue
        # Stem for title_reissue: the canonical's own 《》-core, else any member's,
        # else the canonical's full title.
        rc = inner_core(rep["title"])
        rc = _norm_title(rc) if rc else None
        base = rc if rc and rc in cores else (sorted(cores)[0] if cores else rep["ntitle"])
        anchors[iid] = _anchor_record(rep, members, base)
        for m in members:
            member_to_anchor.setdefault(m["id"], iid)
        for c in cores:
            core_exact.setdefault(c, iid)
    if n_rep_ineligible or n_rep_unloaded:
        print(f"  (skipped {n_rep_ineligible} pools whose canonical is not a central framework "
              f"instrument though a member is; {n_rep_unloaded} whose canonical is outside "
              f"the date window)")
    return anchors, member_to_anchor, core_exact


def build_prov_anchors(docs, central_members):
    """Provincial framework instruments, pooled by instrument_id like the central
    anchors but one anchor per (pool, province). Pools with a central anchor are
    skipped (their provincial members are mirrors of the central text and already
    attributed). The representative is the pool's canonical when it sits in that
    province, else the province's earliest eligible member (first publication).
    Returns (anchors, member_to_anchor, core_exact) where core_exact is keyed by
    (province, normalized core)."""
    pools = defaultdict(list)
    for d in docs.values():
        if d["level"] == "provincial" and d["prov"]:
            pools[d["inst"]].append(d)

    anchors, member_to_anchor, core_exact = {}, {}, {}
    n_central_pool = 0
    for iid, members in pools.items():
        if iid in central_members:
            n_central_pool += 1
            continue
        by_prov = defaultdict(list)
        for m in members:
            by_prov[m["prov"]].append(m)
        for prov, pm in by_prov.items():
            eligible = [m for m in pm if can_anchor(m) and m["date"]]
            if not eligible:
                continue
            cores = named_cores(pm)
            has_auth = any(m["cr"] >= CR_T or m["indeg"] >= DEG_T for m in pm)
            if not (cores or has_auth):
                continue
            canon = [m for m in eligible if m["id"] == iid]
            rep = canon[0] if canon else sorted(eligible, key=lambda m: (m["date"], m["id"]))[0]
            aid = rep["id"]
            core = prov_core(rep["title"])
            base = _norm_title(PLACE_RE.sub("", core)) if core else None
            rec = _anchor_record(rep, pm, base, prov=prov)
            if rec["stem"] and len(rec["stem"]) < PROV_STEM_MIN:
                rec["stem"] = None
            anchors[aid] = rec
            for m in pm:
                member_to_anchor.setdefault(m["id"], aid)
            for c in cores:
                core_exact.setdefault((prov, c), aid)
    if n_central_pool:
        print(f"  (skipped {n_central_pool} provincial pools already anchored centrally)")
    return anchors, member_to_anchor, core_exact


# --------------------------------------------------------------------------- #
# Match                                                                        #
# --------------------------------------------------------------------------- #
def ref_core(target_ref):
    """Exact normalized core of a cited ref: its first 《》 inner, else the whole ref."""
    c = inner_core(target_ref)
    return _norm_title(c) if c else _norm_title(target_ref or "")


def match_citation(conn, docs, anchors, member_to_anchor, core_exact):
    """(source, anchor) pairs from resolved edges to anchor members, plus edges whose
    ref names an anchor by exact 《》-core (recovers mis-resolved mirror citations)."""
    pairs = {}  # (source_id, anchor_id) -> None (set semantics)
    for src, tid, ref in conn.execute(
            "SELECT source_id, target_id, target_ref FROM citations"):
        s = docs.get(src)
        if not s or s["level"] not in SUBNATIONAL:
            continue
        aid = None
        rc = ref_core(ref) if ref else ""
        if GENERIC_FYP_RE.match(rc):
            continue  # bare 五年规划 period mention — resolver noise, not an instrument
        if tid is not None and tid in member_to_anchor:
            aid = member_to_anchor[tid]
        if aid is None and rc:
            aid = core_exact.get(rc)
        if aid is None:
            continue
        if src == aid or src in anchors[aid]["members"]:
            continue
        pairs[(src, aid)] = None
    return pairs


def match_title_and_topic(docs, anchors, cited_pairs):
    """title_reissue via stem/cue match; topic_genre as the bounded residual."""
    stem_index = {}
    for a in anchors.values():
        if a["stem"]:
            stem_index.setdefault(a["stem"], (a["id"],))
    stem_matcher = TitleMatcher(stem_index) if stem_index else None
    cue_anchors = [(c, a["id"]) for a in anchors.values() for c in a["cues"]]

    # topic -> campaign anchors (for topic_genre), pre-sorted by authority desc.
    # Only MAJOR campaigns (cr >= TOPIC_ANCHOR_CR) propose topic_genre implementations
    # — coarse topic tags (Tech/Finance/Commerce) make looser matches too noisy.
    topic_anchors = defaultdict(list)
    for a in anchors.values():
        if a["genre"] in CAMPAIGN_GENRES and a["cr"] >= TOPIC_ANCHOR_CR:
            for t in a["topics"]:
                topic_anchors[t].append(a)
    for t in topic_anchors:
        topic_anchors[t].sort(key=lambda a: -a["cr"])

    title_pairs, topic_pairs = {}, {}
    for s in docs.values():
        if s["level"] not in SUBNATIONAL:
            continue
        title = s["title"]
        if not ISSUANCE_RE.search(title) or NONISSUE_RE.search(title):
            continue
        nt = s["ntitle"]

        # --- title_reissue: stem (named instrument) then quoted X+ cue ---
        matched = None
        if stem_matcher is not None:
            matched = stem_matcher.resolve(nt, STEM_MIN)
        if matched is None:
            for cue, aid in cue_anchors:
                if cue and cue in nt:
                    matched = aid
                    break
        if matched is not None and matched in anchors:
            a = anchors[matched]
            # not a verbatim repost/mirror (anchor's full title inside the candidate)
            if a["ntitle"] and a["ntitle"] in nt:
                matched = None
            elif s["date"] > a["date"] and (s["id"], matched) not in cited_pairs:
                title_pairs[(s["id"], matched)] = None

        # --- topic_genre: bounded residual (one best campaign anchor per source) ---
        if s["genre"] in CAMPAIGN_GENRES or re.search(
                r"(实施方案|行动方案|工作方案|实施意见|行动计划)", title):
            best = None
            seen = set()
            for t in s["topics"]:
                for a in topic_anchors.get(t, []):
                    if a["id"] in seen:
                        continue
                    seen.add(a["id"])
                    if not a["date"] or s["date"] <= a["date"]:
                        continue
                    lag = _lag(s["date"], a["date"])
                    if lag is None or lag > TOPIC_WINDOW:
                        continue
                    if (best is None or a["cr"] > best["cr"]):
                        best = a
            if best is not None:
                pair = (s["id"], best["id"])
                if pair not in cited_pairs and pair not in title_pairs:
                    topic_pairs[pair] = None
    return title_pairs, topic_pairs


def match_citation_prov(conn, docs, anchors, member_to_anchor, core_exact):
    """Provincial-anchor citation pairs: sub-provincial source → anchor member (or
    exact 《》-core) in the SAME province only."""
    pairs = {}
    for src, tid, ref in conn.execute(
            "SELECT source_id, target_id, target_ref FROM citations"):
        s = docs.get(src)
        if not s or s["level"] not in SUBPROVINCIAL:
            continue
        prov = s["prov"]
        if not prov:
            continue
        aid = None
        rc = ref_core(ref) if ref else ""
        if GENERIC_FYP_RE.match(rc):
            continue
        if tid is not None and tid in member_to_anchor:
            aid = member_to_anchor[tid]
        if aid is None and rc:
            aid = core_exact.get((prov, rc))
        if aid is None or anchors[aid]["prov"] != prov:
            continue
        if src == aid or src in anchors[aid]["members"]:
            continue
        pairs[(src, aid)] = None
    return pairs


def match_title_and_topic_prov(docs, anchors, cited_pairs):
    """title_reissue / topic_genre against provincial anchors, per province.
    Stem matching requires the anchor's stem INSIDE the candidate title (memo §1)
    and, when a province issued several instruments with one stem, takes the
    latest one dated before the candidate."""
    stem_anchors = defaultdict(lambda: defaultdict(list))  # prov -> stem -> [anchors]
    cue_anchors = defaultdict(list)                          # prov -> [(cue, aid)]
    topic_anchors = defaultdict(lambda: defaultdict(list))  # prov -> topic -> [anchors]
    for a in anchors.values():
        p = a["prov"]
        if a["stem"]:
            stem_anchors[p][a["stem"]].append(a)
        for c in a["cues"]:
            cue_anchors[p].append((c, a["id"]))
        if a["genre"] in CAMPAIGN_GENRES and a["cr"] >= TOPIC_ANCHOR_CR:
            for t in a["topics"]:
                topic_anchors[p][t].append(a)
    matchers, id_to_stem = {}, {}
    for p, stems in stem_anchors.items():
        index = {}
        for stem, alist in stems.items():
            alist.sort(key=lambda a: a["date"])
            index[stem] = (alist[0]["id"],)
            id_to_stem[alist[0]["id"]] = stem
        matchers[p] = TitleMatcher(index)

    title_pairs, topic_pairs = {}, {}
    for s in docs.values():
        if s["level"] not in SUBPROVINCIAL:
            continue
        prov = s["prov"]
        if not prov or (prov not in stem_anchors and prov not in cue_anchors
                        and prov not in topic_anchors):
            continue
        title = s["title"]
        if not ISSUANCE_RE.search(title) or NONISSUE_RE.search(title):
            continue
        nt = s["ntitle"]

        matched = None
        m = matchers.get(prov)
        if m is not None:
            hit = m.resolve(nt, PROV_STEM_MIN)
            if hit is not None:
                stem = id_to_stem.get(hit)
                if stem and stem in nt:
                    cands = [a for a in stem_anchors[prov][stem] if a["date"] < s["date"]]
                    if cands:
                        matched = cands[-1]["id"]
        if matched is None:
            for cue, aid in cue_anchors.get(prov, []):
                if cue and cue in nt and anchors[aid]["date"] < s["date"]:
                    matched = aid
                    break
        if matched is not None:
            a = anchors[matched]
            if not (a["ntitle"] and a["ntitle"] in nt) and (s["id"], matched) not in cited_pairs:
                title_pairs[(s["id"], matched)] = None

        if s["genre"] in CAMPAIGN_GENRES or re.search(
                r"(实施方案|行动方案|工作方案|实施意见|行动计划)", title):
            best, seen = None, set()
            for t in s["topics"]:
                for a in topic_anchors[prov].get(t, []):
                    if a["id"] in seen:
                        continue
                    seen.add(a["id"])
                    if not a["date"] or s["date"] <= a["date"]:
                        continue
                    lag = _lag(s["date"], a["date"])
                    if lag is None or lag > TOPIC_WINDOW:
                        continue
                    if best is None or a["cr"] > best["cr"]:
                        best = a
            if best is not None:
                pair = (s["id"], best["id"])
                if pair not in cited_pairs and pair not in title_pairs:
                    topic_pairs[pair] = None
    return title_pairs, topic_pairs


def assemble(docs, anchors, cited, title_r, topic_g, anchor_level="central"):
    """One row per (source, anchor), strongest match_type wins."""
    rows, best = [], {}
    for mtype, pairs in (("citation", cited), ("title_reissue", title_r), ("topic_genre", topic_g)):
        for (src, aid) in pairs:
            if (src, aid) in best:
                continue
            best[(src, aid)] = mtype
            s, a = docs[src], anchors[aid]
            lag = _lag(s["date"], a["date"])
            if lag is None or lag < 0 or lag > MAX_LAG:
                continue
            rows.append((
                src, aid, mtype, lag,
                (a["topics"][0] if a["topics"] else ""),
                s["level"], a["date"], s["date"],
                a["title"][:200], s["title"][:200],
                anchor_level, is_implementing(s, mtype),
            ))
    return rows


# --------------------------------------------------------------------------- #
# Write                                                                        #
# --------------------------------------------------------------------------- #
DDL = """
CREATE TABLE IF NOT EXISTS diffusion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL,
    anchor_id INTEGER NOT NULL,
    match_type TEXT NOT NULL,
    lag_days INTEGER,
    topic TEXT,
    source_level TEXT,
    anchor_date TEXT,
    source_date TEXT,
    anchor_title TEXT,
    source_title TEXT,
    anchor_level TEXT NOT NULL DEFAULT 'central',
    source_implementing INTEGER NOT NULL DEFAULT 1,
    UNIQUE(source_id, anchor_id)
);
CREATE INDEX IF NOT EXISTS idx_diffusion_anchor ON diffusion_events(anchor_id);
CREATE INDEX IF NOT EXISTS idx_diffusion_source ON diffusion_events(source_id);
CREATE INDEX IF NOT EXISTS idx_diffusion_type ON diffusion_events(match_type);
"""
# Older tables need the columns added (CREATE IF NOT EXISTS won't).
MIGRATE = {
    "anchor_level":
        "ALTER TABLE diffusion_events ADD COLUMN anchor_level TEXT NOT NULL DEFAULT 'central';",
    "source_implementing":
        "ALTER TABLE diffusion_events ADD COLUMN source_implementing INTEGER NOT NULL DEFAULT 1;",
}
IDX_EXTRA = """
CREATE INDEX IF NOT EXISTS idx_diffusion_anchor_level ON diffusion_events(anchor_level);
CREATE INDEX IF NOT EXISTS idx_diffusion_implementing ON diffusion_events(source_implementing);
"""


def write_table(dbpath, rows):
    conn = sqlite3.connect(dbpath, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    for attempt in range(6):
        try:
            conn.executescript(DDL)
            cols = {r[1] for r in conn.execute("PRAGMA table_info(diffusion_events)")}
            for col, ddl in MIGRATE.items():
                if col not in cols:
                    conn.executescript(ddl)
            conn.executescript(IDX_EXTRA)
            conn.execute("DELETE FROM diffusion_events")
            conn.executemany(
                """INSERT OR REPLACE INTO diffusion_events
                   (source_id, anchor_id, match_type, lag_days, topic, source_level,
                    anchor_date, source_date, anchor_title, source_title, anchor_level,
                    source_implementing)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            wait = (attempt + 1) * 10
            print(f"  DB busy ({e}); retry in {wait}s ({attempt + 1}/6)")
            time.sleep(wait)
    else:
        conn.close()
        sys.exit("ERROR: could not acquire write lock")
    n, n_impl = conn.execute(
        "SELECT COUNT(*), SUM(source_implementing) FROM diffusion_events").fetchone()
    conn.close()
    print(f"\nWrote {n} rows to diffusion_events ({n_impl} implementing, {n - n_impl} mentions)")


# --------------------------------------------------------------------------- #
# Report + validate                                                            #
# --------------------------------------------------------------------------- #
def report(rows, anchors, docs, label="central"):
    by_type = Counter(r[2] for r in rows)
    impl_by_type = Counter(r[2] for r in rows if r[11])
    print(f"\nTotal {label}-anchor diffusion events: {len(rows)} "
          f"(distinct anchors: {len({r[1] for r in rows})}; "
          f"implementing {sum(impl_by_type.values())}, "
          f"mentions {len(rows) - sum(impl_by_type.values())})")
    for t in ("citation", "title_reissue", "topic_genre"):
        print(f"  {t:<14}{by_type.get(t, 0):>6}  (implementing {impl_by_type.get(t, 0)})")
    # Headline ranks by CONFIRMED + IMPLEMENTING signals only (citation + title_reissue,
    # source_implementing=1); topic_genre is a lower-confidence residual and would
    # turn high-cr anchors into magnets, and mentions are references, not cascades.
    per_anchor = Counter()
    localities = defaultdict(set)
    for r in rows:
        if r[2] == "topic_genre" or not r[11]:
            continue
        per_anchor[r[1]] += 1
        localities[r[1]].add(docs[r[0]]["site"])
    print(f"\nTop 5 most-cascaded {label} anchors (distinct implementing localities, "
          "citation+title_reissue, implementing-only):")
    top = sorted(localities.items(), key=lambda kv: (-len(kv[1]), -per_anchor[kv[0]]))[:5]
    for aid, sites in top:
        a = anchors[aid]
        print(f"  {len(sites):>3} localities | {per_anchor[aid]:>3} events | "
              f"{a['date']} | {a.get('prov', '')} | {a['title'][:52]}")


def validate(docs, rows, anchors, prov_rows=None, prov_anchors=None):
    by_anchor = defaultdict(list)
    for r in rows:
        by_anchor[r[1]].append(r)

    def cascade(label, doc_ids):
        # the named docs may be mirrors — resolve each to its pool's anchor id
        aids = sorted({docs[i]["inst"] for i in doc_ids if i in docs} & set(anchors))
        evs = [r for aid in aids for r in by_anchor.get(aid, [])]
        print(f"\n[{label}] docs={doc_ids} -> anchors={aids}")
        if not evs:
            print("  (no events)")
            return
        impl = [r for r in evs if r[11]]
        lags = sorted(r[3] for r in impl if r[3] is not None)
        n = len(lags)
        med = lags[n // 2] if n else None
        print(f"  events={len(evs)} (implementing {len(impl)}, mentions {len(evs) - len(impl)})  "
              f"distinct sites={len({r[5] + r[9] for r in evs})}  "
              f"implementing median lag={med}d  min={lags[0] if lags else '-'}  "
              f"max={lags[-1] if lags else '-'}")
        by_type = Counter(r[2] for r in evs)
        print(f"  by type: {dict(by_type)}  implementing by type: {dict(Counter(r[2] for r in impl))}")
        for r in sorted(evs, key=lambda r: r[7])[:10]:
            # r = (src, aid, mtype, lag, topic, level, adate, sdate, atitle, stitle, alevel, impl)
            print(f"    {r[7]} {r[5]:<11} lag={r[3]:>4} {r[2]:<13} "
                  f"{'impl' if r[11] else 'MENT'} {r[9][:40]}")

    print("\n" + "=" * 78 + "\nVALIDATION\n" + "=" * 78)
    # Specific canonical anchor ids (the trade-in central family; boost; AI+).
    cascade("CONSUMPTION 以旧换新 trade-in (2024-03-13)", [900039931, 900047223, 900047235])
    cascade("CONSUMPTION 提振消费 boost (2025-03-16)", [12650974])
    cascade("AI+ 人工智能+ (2025-08-26)", [900039770])

    if prov_rows is not None:
        by_anchor.clear()
        for r in prov_rows:
            by_anchor[r[1]].append(r)
        anchors = prov_anchors
        # Guangdong's 2024 trade-in instruments (fidelity-provincial.md §5): the
        # 省政府 实施方案, the two 办公厅 行动方案, the 超长期特别国债 实施方案 (+ its mirror).
        cascade("PROVINCIAL 广东 以旧换新 (2024-04-13)", [4406243, 4406240, 4406241, 4518476, 4485000])


# --------------------------------------------------------------------------- #
# Geo self-test + coverage report (read-only)                                  #
# --------------------------------------------------------------------------- #
# Display names as the live `sites` table carries them (2026-10), so the test runs
# without a DB and pins the shapes the fallback must parse.
_GEO_TEST_SITES = {
    "szd_zjg": "Zhangjiagang (苏州张家港市)", "szdp": "Dapeng New District",
    "nanjing": "南京市", "wuhan": "Wuhan Municipality",
    "whd_qiaokou": "Wuhan Qiaokou District (武汉硚口区)", "suzhou_ah": "Suzhou, Anhui (宿州市)",
    "jcgov": "晋城市", "xa": "西安市", "hbqj": "潜江市", "xlgl": "锡林郭勒盟",
    "shijiazhuang": "Shijiazhuang (石家庄市)", "abazhou": "阿坝藏族羌族自治州",
    "linxia": "Linxia Hui Prefecture (临夏回族自治州)", "laiwu": "Laiwu (莱芜)",
    "bjd_daxing": "Beijing Daxing District (北京大兴区)", "cq": "Chongqing Municipality",
    "yushu": "Yushu (玉树藏族自治州)", "zzz_nowhere": "Nowhere Portal",
    "qianjiang": "Qianjiang (潜江市)", "bjrd": "Beijing Municipal People's Congress (北京市人大)",
}
_GEO_TEST_CASES = [
    ("qianjiang", "cq"),   # override beats a wrong display name (see _PROV_EXACT)
    ("bjrd", "bj"),        # geo: leading city/province prefix of an institution name
    ("szd_zjg", "js"), ("szdp", "gd"), ("nanjing", "js"), ("wuhan", "hb"),
    ("whd_qiaokou", "hb"), ("suzhou_ah", "ah"), ("jcgov", "sx"), ("xa", "sn"),
    ("hbqj", "hb"), ("xlgl", "nm"), ("shijiazhuang", "he"), ("abazhou", "sc"),
    ("linxia", "gs"), ("laiwu", "sd"), ("bjd_daxing", "bj"), ("cq", "cq"),
    ("yushu", "qh"), ("zzz_nowhere", None), ("zzz_noname", None),
]


def self_test_geo():
    bad = []
    for site, want in _GEO_TEST_CASES:
        got = province_of(site, _GEO_TEST_SITES.get(site, ""))
        if got != want:
            bad.append((site, want, got))
    for site, want, got in bad:
        print(f"  FAIL {site}: want {want!r} got {got!r}")
    # every code the hand table emits must be a known province code
    stray = {c for c in _PROV_EXACT.values()} | {c for _, c in _PROV_PREFIX}
    stray -= set(PROVINCE_CODE.values())
    if stray:
        bad.append(("hand-table codes", "known", stray))
        print(f"  FAIL hand table emits codes geo does not know: {sorted(stray)}")
    print(f"geo self-test: {len(_GEO_TEST_CASES) + 1 - len(bad)}/{len(_GEO_TEST_CASES) + 1} passed")
    return not bad


def geo_report(conn):
    """Read-only: municipal/district sites resolved by the hand table alone vs with
    the site-name fallback, with doc counts, and the sites still unresolved."""
    load_site_names(conn)
    rows = conn.execute(
        """SELECT s.site_key, s.name, s.admin_level, COUNT(d.id)
           FROM sites s LEFT JOIN documents d ON d.site_key = s.site_key
           WHERE s.admin_level IN ('municipal', 'district')
           GROUP BY s.site_key ORDER BY COUNT(d.id) DESC""").fetchall()
    n_sites = len(rows)
    n_docs = sum(r[3] for r in rows)
    before = [r for r in rows if province_of_override(r[0])]
    after = [r for r in rows if province_of(r[0])]
    print(f"municipal/district sites: {n_sites} ({n_docs} docs)")
    print(f"  hand table only : {len(before):>4} sites / {sum(r[3] for r in before):>6} docs")
    print(f"  + name fallback : {len(after):>4} sites / {sum(r[3] for r in after):>6} docs")
    gained = [r for r in after if not province_of_override(r[0])]
    print(f"  gained by fallback ({len(gained)} sites / {sum(r[3] for r in gained)} docs):")
    for sk, name, lvl, n in gained:
        print(f"    {sk:<16}{province_of(sk):<4}{n:>6}  {name}")
    left = [r for r in rows if not province_of(r[0])]
    print(f"  still unresolved ({len(left)} sites / {sum(r[3] for r in left)} docs):")
    for sk, name, lvl, n in left:
        print(f"    {sk:<16}{lvl:<10}{n:>6}  {name!r}")
    # disagreements between the layers are the hand table's bugs-in-waiting
    for sk, name, lvl, n in rows:
        a, b = province_of_override(sk), province_code_of_site_name(name)
        if a and b and a != b:
            print(f"  DISAGREE {sk}: hand table {a} vs name {b} ({name})")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--write", action="store_true", help="write the diffusion_events table")
    ap.add_argument("--validate", action="store_true", help="print validation cascades")
    ap.add_argument("--self-test-geo", action="store_true",
                    help="unit-test province_of (hand table + site-name fallback), no DB")
    ap.add_argument("--geo-report", action="store_true",
                    help="read-only: which municipal/district sites province_of resolves")
    args = ap.parse_args()

    if args.self_test_geo:
        sys.exit(0 if self_test_geo() else 1)

    dbpath = Path(args.db)
    if not dbpath.exists():
        sys.exit(f"DB not found: {dbpath}")
    t0 = time.time()
    conn = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    if args.geo_report:
        geo_report(conn)
        conn.close()
        return
    load_site_names(conn)
    docs = load(conn)
    print(f"Loaded {len(docs)} docs in {time.time()-t0:.1f}s")
    _report_unresolved(docs)

    anchors, member_to_anchor, core_exact = build_anchors(docs)
    print(f"Anchors: {len(anchors)} pooled central instruments "
          f"({len(member_to_anchor)} member docs, {len(core_exact)} named cores)")

    cited = match_citation(conn, docs, anchors, member_to_anchor, core_exact)
    title_r, topic_g = match_title_and_topic(docs, anchors, cited)
    print(f"Raw pairs: citation={len(cited)} title_reissue={len(title_r)} topic_genre={len(topic_g)}")
    rows = assemble(docs, anchors, cited, title_r, topic_g)
    report(rows, anchors, docs)

    # Second anchor class: provincial framework instruments → same-province implementers.
    p_anchors, p_members, p_core = build_prov_anchors(docs, member_to_anchor)
    print(f"\nProvincial anchors: {len(p_anchors)} pooled instruments "
          f"({len(p_members)} member docs, {len(p_core)} named cores, "
          f"{len({a['prov'] for a in p_anchors.values()})} provinces)")
    p_cited = match_citation_prov(conn, docs, p_anchors, p_members, p_core)
    p_title, p_topic = match_title_and_topic_prov(docs, p_anchors, p_cited)
    conn.close()
    print(f"Raw provincial pairs: citation={len(p_cited)} title_reissue={len(p_title)} "
          f"topic_genre={len(p_topic)}")
    p_rows = assemble(docs, p_anchors, p_cited, p_title, p_topic, anchor_level="provincial")
    report(p_rows, p_anchors, docs, label="provincial")

    if args.validate:
        validate(docs, rows, anchors, p_rows, p_anchors)
    print(f"\nElapsed {time.time()-t0:.1f}s")

    if args.write:
        write_table(str(dbpath), rows + p_rows)
    else:
        print("\n[dry run — nothing written; pass --write to build the table]")


if __name__ == "__main__":
    main()
