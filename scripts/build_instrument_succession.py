#!/usr/bin/env python3
"""Build the `instrument_succession` side table (corpus-lessons A2b): which
instrument REPLACED which, as instrument -> instrument edges.

WHY. The identity layer (`doc_identity.instrument_id`) pools copies of ONE text.
It does not know that the 2019 政府信息公开条例 replaced the 2007 one, that a
试行办法 became the formal 办法, that a 试点方案 was rolled out nationally under a
new name, or that a notice says 原《X》同时废止. The successor-detector memo
(`docs/research/successor-detector.md`) showed the pilots-that-scale gap is mostly
this: pilots scale under NEW NAMES. This table is the renaming layer.

DATA SHAPE
----------
    instrument_succession(
        instrument_id INTEGER,   -- predecessor: a canonical doc_identity.instrument_id
        successor_id  INTEGER,   -- successor:   a canonical doc_identity.instrument_id
        relation      TEXT,      -- superseded_by_stated | revised_edition | renamed | pilot_to_national
        confidence    REAL,      -- 0-1, rule-based (see CONFIDENCE below)
        evidence      TEXT,      -- rule tag + the matched text / key, human-readable
        lag_days      INTEGER,   -- successor date minus predecessor date (> 0 always)
        PRIMARY KEY (instrument_id, relation))

  Universe: doc_identity rows with instrument_role in (canonical, unique), genre in
  (promulgation, implementing), date_quality = 'good'. One row per instrument.
  Dedup rule: ONE successor per predecessor per relation. Among candidates keep the
  highest confidence, then the shortest lag, then the lowest successor id. A
  predecessor may therefore carry up to four rows (one per relation) and a
  successor may be named by many predecessors (a consolidating instrument).
  Cycles are impossible: every edge requires successor.date > predecessor.date,
  strictly, so the graph is a DAG by construction. Self-edges (same instrument_id)
  are dropped before scoring.

RULES (priority order = confidence order)
-----------------------------------------
  1. superseded_by_stated  The successor's BODY names the predecessor in a repeal
     sentence: 《X》(文号) 同时废止 / 原《X》…废止 / 自本办法施行之日起《X》废止 /
     …予以废止. The sentence must carry a 《》 title or a 文号 and must not be a
     procedural clause (修改或者废止, 应当…废止, 清理…, 相抵触…). X resolves to an
     instrument by exact normalized title / title-core (edition-aware: the latest
     edition dated BEFORE the successor; 暂行/试行 are NOT folded, a reference to
     the 暂行办法 is not a reference to the 办法) or by 文号. Confidence 0.95; 0.75
     when the sentence repeals only parts (第N条 / 中的…部分 / 所附清单). A successor
     titled 废止/失效/清理 (a repeal decision) is not a successor.
  2. revised_edition  Same edition-stripped core (years, 修订/修正, 试行/暂行, 版
     removed), same locality (`localize()`), same pilot status, later date, and the
     same lead issuer (0.85) or at least the same admin level (0.70). The nearest
     later edition wins (chains A->B->C come out as two edges).
  3. renamed  Same THEME (successor_detector.theme_core plus form nouns: masthead,
     genre words, years, pilot/edition markers stripped) but a DIFFERENT edition
     core, same locality, same pilot status, later date, and the SAME lead issuer
     (0.65). This is the 管理暂行办法 -> 条例, 实施方案 -> 行动计划 class. Refused:
     generic themes (GENERIC_STEM_RE, or > RENAME_MAX_GROUP instruments at one
     locality), wave markers (第二批/第三期), one core a prefix of the other (法 ->
     法实施条例 is an implementing text), and recurring administrative series
     (_ADMIN_SERIES_RE). The first hand-check (level-only, no exclusions) was 15%
     precise; these exclusions come from its failure classes.
  4. pilot_to_national  Central: successor_detector.detect() (core similarity +
     topic + generalization cue + issuer + citation, threshold 0.62); confidence =
     the detector score. Sub-national: pilot-cued title whose de-piloted theme equals
     a later non-pilot instrument at the same locality, same issuer/level (0.70).
  Boost: +0.05 when the successor cites the predecessor (`citations`), +0.10 when a
  title-rule pair is ALSO stated in the body (the stated row is kept too). Cap 1.0.

USAGE (repo root; the DB is the droplet's documents.db)
-------------------------------------------------------
    python3 scripts/build_instrument_succession.py --self-test
    python3 scripts/build_instrument_succession.py --dry-run             # read-only: counts + 30-row samples
    python3 scripts/build_instrument_succession.py --dry-run --out /tmp/succ --sample 20 --seed 7
    python3 scripts/build_instrument_succession.py --write --force       # nightly (holds the lock itself)

WRITE DISCIPLINE: read-only (?mode=ro) unless --write. One transaction, touches
only `instrument_succession`. Refuses to write while the nightly lock exists
unless --force. Depends on doc_identity (run after build_doc_identity.py) and
on the citations table (boost only).
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
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "citations"))
sys.path.insert(0, str(ROOT / "scripts" / "rnd" / "analysis"))

from extract_citations import _norm_title, _title_cores_of_title, _agg_docnum, _CORE_DOCNUM  # noqa: E402
from build_doc_identity import (  # noqa: E402
    title_core, _best_core, localize, LEVEL_RANK, GENERIC_STEM_RE, KEY_MIN, LOCK_DIR, _to_date, connect)
import successor_detector as sd  # noqa: E402

DB_PATH = ROOT / "documents.db"
UNIVERSE_GENRES = ("promulgation", "implementing")
RENAME_MAX_GROUP = 6      # a theme shared by more instruments at one locality is generic
THEME_MIN = 6             # normalized theme chars for a renamed match
PILOT_THRESHOLD = 0.62    # successor_detector's validated threshold

CONF = {
    "stated": 0.95, "stated_partial": 0.75,
    "edition_issuer": 0.85, "edition_level": 0.70,
    "renamed_issuer": 0.65,
    "pilot_subnational": 0.70,
}
BOOST_CITE, BOOST_STATED = 0.05, 0.10

# --------------------------------------------------------------------------- #
# Edition markers                                                              #
# --------------------------------------------------------------------------- #
# Stripped from a raw core to obtain the edition-free core. Years in any bracket
# style, 修订/修正 tags, 试行/暂行, 版 tags, 第N次修正. NOT the pilot markers
# (试点/试验区 ...): pilot status is compared separately.
_EDITION_RE = re.compile(
    r"[（(〔\[]?\s*(?:19|20)\d{2}\s*年?\s*(?:版|修订|修正|修订版|修订稿|修改)?\s*[)）〕\]]?"
    r"|[（(]\s*(?:修订|修正|修订版|修订稿|修改|试行|暂行|草案|征求意见稿|新版|最新版)\s*[)）]"
    r"|第[一二三四五六七八九十\d]+次修订|第[一二三四五六七八九十\d]+次修正|修订版|修订稿|修订本"
    r"|试行|暂行|新版")


def edition_core(title):
    """Edition-free normalized core of a title ('' when too short)."""
    raw, key = _best_core(title)
    if key is None:
        return ""
    s = _norm_title(_EDITION_RE.sub("", raw))
    return s if len(s) >= KEY_MIN else ""


# Instrument-form nouns the detector's theme_core leaves in place (it strips 办法/
# 规定/方案/意见 but not 条例/细则/规划 ...). A rename is precisely a change of form,
# so the theme must be form-free. Applied repeatedly (实施细则 -> '' in two steps).
_FORM_NOUN_RE = re.compile(
    r"(?:行动|总体|指导|若干|实施|条例|细则|规则|规范|规划|纲要|计划|措施|指南|指引|标准|"
    r"目录|清单|准则|要点|预案|章程|守则|规程|方案|办法|规定|意见|决定|通知|公告|通告|法)$")


def theme_of(title):
    # edition markers go first: the detector's masthead regex reads 暂行 as an issuer
    # ending in 行 and would eat '城镇燃气管理暂行' whole
    t = sd.theme_core(_EDITION_RE.sub("", title or ""), _norm_title, _title_cores_of_title)
    for _ in range(3):
        nt = _FORM_NOUN_RE.sub("", t)
        if nt == t:
            break
        t = nt
    return t if len(t) >= 4 else ""


def is_pilot(title):
    return bool(sd.PILOT_RE.search(title or ""))


# --------------------------------------------------------------------------- #
# Repeal sentences                                                             #
# --------------------------------------------------------------------------- #
_SENT_SPLIT = re.compile(r"[。；;\n\r]")
_REPEAL_RE = re.compile(r"同时废止|予以废止|起废止|之日起.{0,12}废止|即行废止|同时失效|废止\s*$|停止执行\s*$")
# procedural / hedged clauses: the sentence talks ABOUT repealing, it does not repeal
_PROCEDURAL_RE = re.compile(
    r"修改或者?废止|修订或者?废止|、废止|废止、|保留|清理|评估|应当|应该|可以|可根据|建议|是否|"
    r"相抵触|抵触|不一致|不符|为准|除外|另行|有效期|届满|程序|备案|目录|审查|公布.{0,6}废止|"
    r"宣布失效|确认失效|失效的|决定废止|予以废止的|废止的|废止文件清单|"
    # a site annotation saying THIS document was repealed by a later one
    r"本(?:文|通知|公告|办法|规定|意见|条例|细则|方案|规则)(?:自[^，,]{0,24})?(?:全文)?(?:废止|失效)")
# a successor must be an instrument, not a repeal / clean-up decision
_REPEAL_TITLE_RE = re.compile(r"废止|失效|清理")
_QUOTED_RE = re.compile(r"《([^《》]{4,120})》")
_INNER_RE = re.compile(r"[〈<]([^〈〉<>]{4,120})[〉>]")
_PARTIAL_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+[条款项章节]|中的|所附|部分|有关.{0,8}规定|相关.{0,8}规定|附件\d*|附表")
_DOCNUM_TAIL_RE = re.compile(r"[（(][^（()）]*?(?:19|20)\d{2}[^（()）]*?\d+\s*号\s*[)）]\s*$")
_FEIZHI_FTS = " OR ".join(f'body_text_cn: "{p}"' for p in (
    "时废止", "予以废止", "起废止", "》废止", "废止。", "废止；", "废止，", "废止）", "行废止", "同时失效"))


def repeal_sentences(body):
    """Sentences of a body that state a repeal of a named instrument."""
    out = []
    for s in _SENT_SPLIT.split(body or ""):
        s = s.strip()
        if not s or len(s) > 600 or "废止" not in s and "失效" not in s and "停止执行" not in s:
            continue
        if not _REPEAL_RE.search(s):
            continue
        if not (_QUOTED_RE.search(s) or _CORE_DOCNUM.search(s)):
            continue
        if _PROCEDURAL_RE.search(s):
            continue
        out.append(s)
    return out


_ENACT_RE = re.compile(r"施行|实施|生效|印发|发布|颁布|批准|通过|公布")
_REPEALED_RE = re.compile(r"废止|失效|停止执行")


def _repealed_segment(sentence, end):
    """True when the text after a reference (up to the next 《 or the sentence end)
    repeals it. '《New》已于8月1日起施行，《Old》同时废止' names New as the enacting
    text, not a repealed one: its trailing segment has 施行 and no 废止."""
    nxt = sentence.find("《", end)
    seg = sentence[end:nxt if nxt >= 0 else len(sentence)]
    return not (_ENACT_RE.search(seg) and not _REPEALED_RE.search(seg))


def ref_names(sentence):
    """Candidate title strings named in a repeal sentence (outer 《》 and inner 〈〉),
    each also minus a trailing （文号） group. A reference whose own clause enacts
    rather than repeals (…施行，) is skipped."""
    names = []
    for m in _QUOTED_RE.finditer(sentence):
        if not _repealed_segment(sentence, m.end()):
            continue
        names.append(m.group(1))
        names.extend(_INNER_RE.findall(m.group(1)))
    out = []
    for n in names:
        n = n.strip()
        out.append(n)
        n2 = _DOCNUM_TAIL_RE.sub("", n).strip()
        if n2 != n:
            out.append(n2)
    return out


def ref_keys(name):
    """Normalized lookup keys for a referenced title: the whole name, its
    institutional cores, and its edition-free form."""
    keys = []
    nt = _norm_title(title_core(name))
    if len(nt) >= KEY_MIN:
        keys.append(nt)
    for core, flag in _title_cores_of_title(name):
        if flag == 1:
            nc = _norm_title(core)
            if len(nc) >= KEY_MIN:
                keys.append(nc)
    # NO edition-free key here: an explicit reference to the 1982 暂行办法 must not
    # resolve to the 1989 办法 that replaced it (hand-check round 3)
    seen, out = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            out.append(k)
    return out


_DOCNUM_LEAD = re.compile(r"^(?:原|即|原则上|依据|按照|根据|和|及|与|的)+")


def docnums_in(sentence):
    """Aggressive 文号 keys named in a sentence. The issuer prefix is tried as matched
    and with a leading connective removed (原阳府〔2009〕21号 -> 阳府200921号)."""
    out = []
    for m in _CORE_DOCNUM.finditer(sentence):
        if not _repealed_segment(sentence, m.end()):
            continue
        pre = m.group(1)
        out.append(_agg_docnum(f"{pre}{m.group(2)}{m.group(3)}号"))
        pre2 = _DOCNUM_LEAD.sub("", pre)
        if pre2 and pre2 != pre:
            out.append(_agg_docnum(f"{pre2}{m.group(2)}{m.group(3)}号"))
    return out


# --------------------------------------------------------------------------- #
# Load                                                                         #
# --------------------------------------------------------------------------- #
UNIVERSE_SQL = """
SELECT di.doc_id, d.title, d.site_key, d.date_published, d.document_number, d.topics_algo,
       di.admin_level_doc, di.lead_issuer, di.genre
FROM doc_identity di JOIN documents d ON d.id = di.doc_id
WHERE di.instrument_role IN ('canonical', 'unique')
  AND di.genre IN ('promulgation', 'implementing')
  AND di.date_quality = 'good'
"""


def load_universe(conn):
    insts = {}
    for (did, title, site, dp, dn, topics, level, issuer, genre) in conn.execute(UNIVERSE_SQL):
        d = _to_date(dp or "")
        if not d or d.year < 1949 or d > date.today():
            continue
        title = title or ""
        insts[did] = {
            "id": did, "title": title, "site": site or "", "date": d, "docnum": dn or "",
            "topics": frozenset(t for t in (topics or "").split(",") if t),
            "level": level or "unknown", "issuer": issuer, "genre": genre, "inst": did, "role": "canonical",
        }
    return insts


def load_doc2inst(conn):
    return dict(conn.execute("SELECT doc_id, instrument_id FROM doc_identity"))


def build_lookup(conn, insts, doc2inst):
    """Title-key and 文号 indexes over ALL documents, mapped to universe instruments:
    key -> list of (date, instrument_id)."""
    by_title, by_docnum = defaultdict(set), defaultdict(set)
    cur = conn.execute("SELECT id, title, document_number FROM documents")
    for did, title, dn in cur:
        inst = doc2inst.get(did)
        if inst not in insts:
            continue
        tc = title_core(title or "")
        keys = set()
        nt = _norm_title(tc)
        if len(nt) >= KEY_MIN:
            keys.add(nt)
        for core, flag in _title_cores_of_title(tc):
            if flag == 1:
                nc = _norm_title(core)
                if len(nc) >= KEY_MIN:
                    keys.add(nc)
        for k in keys:
            by_title[k].add(inst)
        if dn:
            a = _agg_docnum(dn)
            if len(a) >= 6:
                by_docnum[a].add(inst)
        m = list(_CORE_DOCNUM.finditer(tc))
        if m:
            m = m[-1]
            by_docnum[_agg_docnum(f"{m.group(1)}{m.group(2)}{m.group(3)}号")].add(inst)
    return by_title, by_docnum


def load_cites(conn, insts, doc2inst):
    """successor instrument -> set(predecessor instruments it cites), pooled on instrument."""
    cites = defaultdict(set)
    for s, t in conn.execute("SELECT source_id, target_id FROM citations WHERE target_id IS NOT NULL"):
        si, ti = doc2inst.get(s), doc2inst.get(t)
        if si in insts and ti in insts and si != ti:
            cites[si].add(ti)
    return cites


# --------------------------------------------------------------------------- #
# Rule 1: stated repeal                                                        #
# --------------------------------------------------------------------------- #
def _pick_predecessor(cands, insts, succ):
    """Among instruments sharing a key, the latest one dated BEFORE the successor."""
    best = None
    for c in cands:
        p = insts.get(c)
        if not p or c == succ["id"] or p["date"] >= succ["date"]:
            continue
        if best is None or (p["date"], -p["id"]) > (best["date"], -best["id"]):
            best = p
    return best


def stated_pairs_for(succ, body, insts, by_title, by_docnum):
    """-> {pred_id: (confidence, evidence)} from the successor's body."""
    out = {}
    for s in repeal_sentences(body):
        partial = bool(_PARTIAL_RE.search(s))
        found = []
        for name in ref_names(s):
            for k in ref_keys(name):
                p = _pick_predecessor(by_title.get(k, ()), insts, succ)
                if p:
                    found.append((p, f"《{name[:60]}》"))
                    break
        for dn in docnums_in(s):
            p = _pick_predecessor(by_docnum.get(dn, ()), insts, succ)
            if p:
                found.append((p, dn))
        for p, how in found:
            conf = CONF["stated_partial"] if partial else CONF["stated"]
            ev = f"stated{'_partial' if partial else ''}:{how} | {s[-140:]}"
            if p["id"] not in out or out[p["id"]][0] < conf:
                out[p["id"]] = (conf, ev)
    return out


def stated_pairs(conn, insts, doc2inst, by_title, by_docnum):
    ids = [r[0] for r in conn.execute("SELECT rowid FROM doc_search WHERE doc_search MATCH ?", (_FEIZHI_FTS,))]
    pairs = {}  # (pred, succ) -> (conf, ev)
    n_bodies = 0
    for did in ids:
        inst = doc2inst.get(did)
        succ = insts.get(inst)
        if not succ or _REPEAL_TITLE_RE.search(succ["title"]):
            continue
        row = conn.execute("SELECT body_text_cn FROM documents WHERE id=?", (did,)).fetchone()
        if not row or not row[0]:
            continue
        n_bodies += 1
        for pid, (conf, ev) in stated_pairs_for(succ, row[0], insts, by_title, by_docnum).items():
            key = (pid, succ["id"])
            if key not in pairs or pairs[key][0] < conf:
                pairs[key] = (conf, ev)
    return pairs, len(ids), n_bodies


# --------------------------------------------------------------------------- #
# Rules 2-4: title lineage                                                     #
# --------------------------------------------------------------------------- #
def issuer_match(p, q):
    """'issuer' when both lead issuers are known and equal, 'level' when the per-doc
    admin levels agree, else None."""
    if p["issuer"] and q["issuer"] and p["issuer"] == q["issuer"]:
        return "issuer"
    if p["level"] == q["level"] and p["level"] in LEVEL_RANK and LEVEL_RANK[p["level"]] <= 3:
        return "level"
    return None


# Recurring administrative series are not instrument lineages (annual 工作总结,
# 纳税期限 notices, duty rosters, lists of winners). Title rules skip them; the
# stated-repeal channel does not (a body sentence is explicit).
_ADMIN_SERIES_RE = re.compile(
    r"工作总结|总结及|申报.{0,6}期限|纳税期限|放假|值班|分工|领导小组|成员|任免|聘任|名单|名录|"
    r"获奖|表彰|考试|招聘|录用|预算|决算|公报|会议纪要|议事规则|征集|评选|评审结果|公示|中标|"
    r"采购|领取|收取|材料|备案|年报|年度报告|统计|申报|废止部分|修改部分|部分地方性法规|部分规章|"
    r"职务|同志|任职|免职|下达|拨付|划拨")
RENAME_MIN_LAG = 90  # closer than this = unpooled mirror copies, not a renaming
# Waves of one programme (第二批 list, 第三期 call) are not renamings.
_WAVE_RE = re.compile(r"第[一二三四五六七八九十百\d]+(?:批|期|轮|届)")
# A bare decree / notice title carries no instrument name.
_BARE_DECREE_RE = re.compile(r"^[一-鿿]{2,12}(?:人民政府令|政府令|令|公告|通告|公报)$")
DUP_MAX_LAG = 400  # same normalized key within this window = a repost, not an edition


def annotate(insts):
    for d in insts.values():
        stem, loc, _ = localize(d["title"], d["site"])
        d["loc"] = loc or ""
        d["key"] = _best_core(d["title"])[1] or ""
        d["ecore"] = edition_core(d["title"])
        if d["ecore"] and _BARE_DECREE_RE.match(d["ecore"]):
            d["ecore"] = ""
        d["theme"] = theme_of(d["title"])
        d["pilot"] = is_pilot(d["title"])
        d["reply"] = bool(sd.REPLY_RE.search(d["title"]))
        d["admin"] = bool(_ADMIN_SERIES_RE.search(d["title"]))
        d["wave"] = bool(_WAVE_RE.search(d["title"]))


def _nearest_later(members, pred, accept):
    best = None
    for q in members:
        if q["id"] == pred["id"] or q["date"] <= pred["date"]:
            continue
        how = accept(pred, q)
        if not how:
            continue
        key = (q["date"], q["id"])
        if best is None or key < best[0]:
            best = (key, q, how)
    return (best[1], best[2]) if best else (None, None)


def edition_pairs(insts):
    """revised_edition: same edition-free core + locality + pilot status."""
    groups = defaultdict(list)
    for d in insts.values():
        if d["ecore"] and not d["reply"] and not d["admin"]:
            groups[(d["ecore"], d["loc"], d["pilot"])].append(d)
    pairs = {}

    def accept(p, q):
        # an identical normalized title within 400 days is a repost / same-site
        # duplicate the identity layer could not pool (it needs two sites)
        if p["key"] and p["key"] == q["key"] and (q["date"] - p["date"]).days < DUP_MAX_LAG:
            return None
        return issuer_match(p, q)
    for members in groups.values():
        if len(members) < 2:
            continue
        for p in members:
            q, how = _nearest_later(members, p, accept)
            if q:
                conf = CONF["edition_issuer" if how == "issuer" else "edition_level"]
                pairs[(p["id"], q["id"])] = (conf, f"edition:{how} core={p['ecore'][:50]}")
    return pairs


def renamed_pairs(insts):
    """renamed: same theme, different edition-free core, same locality + pilot status."""
    groups = defaultdict(list)
    for d in insts.values():
        if d["theme"] and len(d["theme"]) >= THEME_MIN and not d["reply"] and not d["admin"] \
                and not d["wave"] and not GENERIC_STEM_RE.search(d["theme"]):
            groups[(d["theme"], d["loc"], d["pilot"])].append(d)
    pairs = {}

    def accept(p, q):
        if p["ecore"] and p["ecore"] == q["ecore"]:
            return None  # that is an edition, rule 2's job
        a, b = p["ecore"], q["ecore"]
        if a and b and (a.startswith(b) or b.startswith(a)):
            return None  # 环境保护税法 / 环境保护税法实施条例: implementing text, not a rename
        if (q["date"] - p["date"]).days < RENAME_MIN_LAG:
            return None  # two mastheads for one text, days apart: copies the pooler missed
        # a rename needs the SAME lead issuer; level-only pairs were sibling bureaus'
        # parallel texts in the hand-check
        return "issuer" if issuer_match(p, q) == "issuer" else None
    for members in groups.values():
        if len(members) < 2 or len(members) > RENAME_MAX_GROUP:
            continue
        for p in members:
            q, how = _nearest_later(members, p, accept)
            if q:
                pairs[(p["id"], q["id"])] = (CONF["renamed_issuer"], f"renamed:{how} theme={p['theme'][:40]}")
    return pairs


def pilot_pairs(insts, cites):
    """pilot_to_national: the detector at central, de-piloted theme elsewhere."""
    pairs = {}
    central = [d for d in insts.values() if d["level"] == "central"]
    pilots = [d for d in central if d["pilot"]]
    cands = [d for d in central if not d["pilot"] and not d["reply"]]
    cores = {d["id"]: d["theme"] for d in central}
    # the detector wants pilot -> set(citing successors)
    rev = defaultdict(set)
    for s, ts in cites.items():
        for t in ts:
            rev[t].add(s)
    found = sd.detect(pilots, cands, cores, rev, PILOT_THRESHOLD)
    for pid, (cid, sc) in found.items():
        pairs[(pid, cid)] = (min(1.0, sc["score"]),
                             f"pilot:detector score={sc['score']} kind={sc['kind']} cue={sc['cue']} rel={sc['rel']}")
    # sub-national: exact de-piloted theme at the same locality
    groups = defaultdict(list)
    for d in insts.values():
        if d["level"] != "central" and d["theme"] and len(d["theme"]) >= THEME_MIN and not d["reply"] \
                and not d["admin"] and not GENERIC_STEM_RE.search(d["theme"]):
            groups[(d["theme"], d["loc"])].append(d)
    for members in groups.values():
        ps = [m for m in members if m["pilot"]]
        qs = [m for m in members if not m["pilot"] and not m["wave"]]  # a later wave is not a rollout
        if not ps or not qs or len(members) > RENAME_MAX_GROUP:
            continue
        for p in ps:
            q, how = _nearest_later(qs, p, issuer_match)
            if q:
                pairs[(p["id"], q["id"])] = (CONF["pilot_subnational"], f"pilot:theme {how} theme={p['theme'][:40]}")
    return pairs, len(pilots)


# --------------------------------------------------------------------------- #
# Assemble + dedup                                                             #
# --------------------------------------------------------------------------- #
RELATIONS = ("superseded_by_stated", "revised_edition", "renamed", "pilot_to_national")


def assemble(insts, stated, editions, renamed, pilots, cites):
    """-> list of row dicts after boosts and the one-per-(predecessor, relation) rule."""
    cand = {"superseded_by_stated": stated, "revised_edition": editions, "renamed": renamed,
            "pilot_to_national": pilots}
    best = {}
    for rel, pairs in cand.items():
        for (pid, sid), (conf, ev) in pairs.items():
            p, q = insts.get(pid), insts.get(sid)
            if not p or not q or pid == sid or q["date"] <= p["date"]:
                continue
            if pid in cites.get(sid, ()):
                conf += BOOST_CITE
                ev += " +cite"
            if rel != "superseded_by_stated" and (pid, sid) in stated:
                conf += BOOST_STATED
                ev += " +stated"
            conf = round(min(1.0, conf), 3)
            lag = (q["date"] - p["date"]).days
            key = (pid, rel)
            cur = best.get(key)
            if cur is None or (conf, -lag, -sid) > (cur["confidence"], -cur["lag_days"], -cur["successor_id"]):
                best[key] = {"instrument_id": pid, "successor_id": sid, "relation": rel,
                             "confidence": conf, "evidence": ev, "lag_days": lag}
    return sorted(best.values(), key=lambda r: (r["relation"], r["instrument_id"]))


def build(conn):
    t0 = time.time()
    insts = load_universe(conn)
    doc2inst = load_doc2inst(conn)
    by_title, by_docnum = build_lookup(conn, insts, doc2inst)
    cites = load_cites(conn, insts, doc2inst)
    t_load = time.time() - t0
    annotate(insts)
    stated, n_fts, n_bodies = stated_pairs(conn, insts, doc2inst, by_title, by_docnum)
    t_stated = time.time() - t0 - t_load
    editions = edition_pairs(insts)
    renamed = renamed_pairs(insts)
    pilots, n_pilots = pilot_pairs(insts, cites)
    rows = assemble(insts, stated, editions, renamed, pilots, cites)
    meta = {"n_insts": len(insts), "n_fts": n_fts, "n_bodies": n_bodies, "n_pilots_central": n_pilots,
            "raw": {"stated": len(stated), "edition": len(editions), "renamed": len(renamed), "pilot": len(pilots)},
            "t_load": t_load, "t_stated": t_stated, "t_total": time.time() - t0}
    return insts, rows, meta


# --------------------------------------------------------------------------- #
# Write                                                                        #
# --------------------------------------------------------------------------- #
DDL = """
DROP TABLE IF EXISTS instrument_succession;
CREATE TABLE instrument_succession (
    instrument_id INTEGER NOT NULL,
    successor_id INTEGER NOT NULL,
    relation TEXT NOT NULL,
    confidence REAL NOT NULL,
    evidence TEXT NOT NULL,
    lag_days INTEGER NOT NULL,
    PRIMARY KEY (instrument_id, relation)
);
CREATE INDEX IF NOT EXISTS idx_instrument_succession_succ ON instrument_succession(successor_id);
"""


def write(conn, rows):
    t0 = time.time()
    data = [(r["instrument_id"], r["successor_id"], r["relation"], r["confidence"], r["evidence"], r["lag_days"])
            for r in rows]
    conn.execute("BEGIN IMMEDIATE")
    try:
        for stmt in DDL.strip().split(";"):
            if stmt.strip():
                conn.execute(stmt)
        conn.executemany("INSERT INTO instrument_succession VALUES (?,?,?,?,?,?)", data)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return len(data), time.time() - t0


# --------------------------------------------------------------------------- #
# Report                                                                       #
# --------------------------------------------------------------------------- #
def report(insts, rows, meta, sample_n, seed, out_dir=None):
    print("=" * 100)
    print("INSTRUMENT SUCCESSION (A2b)")
    print("=" * 100)
    print(f"universe: {meta['n_insts']:,} instruments (canonical/unique, promulgation+implementing, good dates)")
    print(f"repeal-sentence channel: {meta['n_fts']:,} FTS hits, {meta['n_bodies']:,} universe bodies read")
    print(f"raw candidate pairs: {meta['raw']}")
    print(f"timing: load {meta['t_load']:.1f}s, stated {meta['t_stated']:.1f}s, total {meta['t_total']:.1f}s")
    by_rel = Counter(r["relation"] for r in rows)
    print(f"\nrows after dedup: {len(rows):,}")
    for rel in RELATIONS:
        rs = [r for r in rows if r["relation"] == rel]
        if not rs:
            print(f"  {rel:<22} 0")
            continue
        lags = sorted(r["lag_days"] for r in rs)
        confs = Counter(r["confidence"] for r in rs)
        print(f"  {rel:<22} {len(rs):>6}  median lag {lags[len(lags)//2]:>5} d  "
              f"conf dist {dict(sorted(confs.items(), reverse=True))}")
    preds = {r["instrument_id"] for r in rows}
    succs = Counter(r["successor_id"] for r in rows)
    print(f"distinct predecessors {len(preds):,}; distinct successors {len(succs):,}; "
          f"max in-degree {max(succs.values()) if succs else 0}")
    by_level = Counter(insts[r["instrument_id"]]["level"] for r in rows)
    print(f"predecessor level: {dict(by_level)}")
    # pilots: share of the detector's central pilot set that now has ANY successor
    pil = [d for d in insts.values() if d["level"] == "central" and d["pilot"]]
    with_any = sum(1 for d in pil if d["id"] in preds)
    with_p2n = sum(1 for d in pil if (d["id"], "pilot_to_national") in {(r["instrument_id"], r["relation"]) for r in rows})
    print(f"\ncentral pilot instruments (detector set): {len(pil):,}; with pilot_to_national {with_p2n} "
          f"({100*with_p2n/len(pil) if pil else 0:.1f}%); with ANY successor relation {with_any} "
          f"({100*with_any/len(pil) if pil else 0:.1f}%)")
    rng = random.Random(seed)
    for rel in RELATIONS:
        rs = [r for r in rows if r["relation"] == rel]
        smp = rng.sample(rs, min(sample_n, len(rs)))
        print(f"\n--- sample {rel} ({len(smp)} of {len(rs)}) ---")
        for r in smp:
            p, q = insts[r["instrument_id"]], insts[r["successor_id"]]
            print(f"  [{r['confidence']:.2f}] {p['date']} {p['id']} {p['title'][:60]}\n"
                  f"      -> {q['date']} {q['id']} {q['title'][:60]}\n"
                  f"      {r['evidence'][:150]}")
        if out_dir:
            out = Path(out_dir)
            out.mkdir(parents=True, exist_ok=True)
            with open(out / f"sample_{rel}.tsv", "w") as fh:
                fh.write("n\tconf\tpred_id\tpred_date\tpred_level\tpred_issuer\tpred_title\tsucc_id\tsucc_date\tsucc_issuer\tsucc_title\tevidence\tverdict\n")
                for i, r in enumerate(smp, 1):
                    p, q = insts[r["instrument_id"]], insts[r["successor_id"]]
                    fh.write("\t".join(str(x) for x in [
                        i, r["confidence"], p["id"], p["date"], p["level"], p["issuer"], p["title"],
                        q["id"], q["date"], q["issuer"], q["title"], r["evidence"].replace("\t", " "), ""]) + "\n")
    if out_dir:
        with open(Path(out_dir) / "pairs.tsv", "w") as fh:
            fh.write("relation\tconf\tlag\tpred_id\tpred_date\tpred_title\tsucc_id\tsucc_date\tsucc_title\tevidence\n")
            for r in rows:
                p, q = insts[r["instrument_id"]], insts[r["successor_id"]]
                fh.write("\t".join(str(x) for x in [
                    r["relation"], r["confidence"], r["lag_days"], p["id"], p["date"], p["title"],
                    q["id"], q["date"], q["title"], r["evidence"].replace("\t", " ")]) + "\n")
        print(f"\nwrote {out_dir}/pairs.tsv + sample_<relation>.tsv")


# --------------------------------------------------------------------------- #
# Self-test                                                                    #
# --------------------------------------------------------------------------- #
_EDITION_TESTS = [
    ("政府信息公开条例", "政府信息公开条例（2019年修订）", True),
    ("深圳市行政过错责任追究办法（试行）", "深圳市行政过错责任追究办法", True),
    ("关于印发《上海市公共图书馆管理暂行办法》的通知", "上海市公共图书馆管理办法", True),
    ("企业所得税年度纳税申报表（A类，2017年版）", "企业所得税年度纳税申报表（A类，2020年版）", True),
    ("广东省小企业创业基地确认管理试行办法", "小型微型企业创业创新示范基地建设管理办法", False),
    ("城乡规划法实施办法", "土地管理法实施办法", False),
]
_THEME_TESTS = [
    ("国务院关于印发《城镇燃气管理暂行办法》的通知", "城镇燃气管理条例", True),
    ("深圳市知识产权保护试点工作方案", "深圳市知识产权保护工作方案", True),
    ("关于加快推进政务服务标准化的实施意见", "关于加快推进政务数据共享的实施意见", False),
]
_SENTENCE_TESTS = [
    ("《阳江市政府投资项目管理暂行办法》（阳府〔2009〕21号）同时废止", 1),
    ("原《河源市城乡居民社会养老保险实施办法》（河源市人民政府令第5号）同时废止", 1),
    ("本办法自2020年1月1日起施行，《深圳市行政过错责任追究办法》自本办法实施之日起废止", 1),
    ("《国土资源部关于加强地质资料管理的通知》（国土资规〔2017〕1号）、《自然资源部办公厅关于进一步做好地质资料汇交管理的通知》同时废止", 1),
    ("凡与《条例》相抵触或者不一致的，应当及时予以修改或者废止", 0),
    ("清理后应当向社会公布继续有效、废止和失效的规范性文件目录", 0),
    ("立法后评估报告是修改废止规章、完善配套制度和改进实施措施的主要参考依据", 0),
    ("在有效期内，可根据实际情况按规定进行修改或废止", 0),
    ("本办法自发布之日起施行", 0),
    ("原江府〔1998〕54号文同时废止", 1),
    ("根据《国家税务总局关于下发全国税务机关出口退（免）税管理工作规范（1.1版）的通知》(税总发〔2015〕162号)及附件41《废止文件清单》，本文废止", 0),
    ("本通知自2024年1月1日起全文废止", 0),
]
_PARTIAL_TESTS = [
    ("《国家税务总局关于使用新版机动车销售统一发票有关问题的通知》（国税函〔2006〕479号）第五条自本办法试行之日起废止", True),
    ("《广州市城乡居民社会养老保险试行办法》（穗府办〔2012〕34号）同时废止", False),
]
_REFNAME_TESTS = [
    ("《关于印发〈广东省小企业创业基地确认管理试行办法〉的通知》（粤中小企〔2010〕31号）同时废止",
     "广东省小企业创业基地确认管理试行办法"),
    ("《财政部 税务总局关于广告费支出税前扣除有关事项的公告》（财政部 税务总局公告2020年第43号）自2026年1月1日起废止",
     "财政部 税务总局关于广告费支出税前扣除有关事项的公告"),
]
_ENACT_TESTS = [
    # (sentence, name that must NOT be returned, name that must be returned)
    ("381号令《城市生活无着的流浪乞讨人员救助管理办法》已于今年8月1日起施行，《城市流浪乞讨人员收容遣送办法》同时被废止",
     "城市生活无着的流浪乞讨人员救助管理办法", "城市流浪乞讨人员收容遣送办法"),
    ("本办法自2020年1月1日起施行，《深圳市行政过错责任追究办法》自本办法实施之日起废止",
     None, "深圳市行政过错责任追究办法"),
]
_D = date


def _inst(i, title, d, level="central", issuer="国务院", site="gov"):
    return {"id": i, "title": title, "site": site, "date": d, "docnum": "", "topics": frozenset(),
            "level": level, "issuer": issuer, "genre": "promulgation", "inst": i, "role": "canonical"}


_LINEAGE_TESTS = [
    # (instruments, expected {(pred, rel): succ})
    # a 试行 -> formal edition, same issuer; a 2019 revision 400d+ later; chain A->B->C
    ([_inst(1, "国务院关于印发《政府信息公开条例（试行）》的通知", _D(2007, 4, 5)),
      _inst(2, "政府信息公开条例", _D(2008, 5, 1)),
      _inst(3, "政府信息公开条例（2019年修订）", _D(2019, 4, 3))],
     {(1, "revised_edition"): 2, (2, "revised_edition"): 3}),
    # renamed: 暂行办法 -> 条例, same issuer; no edition edge because cores differ
    ([_inst(10, "国务院关于印发《城镇燃气管理暂行办法》的通知", _D(2005, 1, 1)),
      _inst(11, "城镇燃气管理条例", _D(2010, 10, 19))],
     {(10, "renamed"): 11}),
    # different localities never pair, even with one stem (深圳 vs 广州 offices)
    ([_inst(20, "深圳市人民政府关于印发《深圳市政府投资项目管理办法》的通知", _D(2010, 1, 1), "municipal", "深圳市人民政府", "sz"),
      _inst(21, "广州市人民政府关于印发《广州市政府投资项目管理办法》的通知", _D(2012, 1, 1), "municipal", "广州市人民政府", "gz")],
     {}),
    # same locality, later edition at the same level but a different bureau: level match
    ([_inst(30, "深圳市人民政府关于印发《深圳市政府投资项目管理办法（试行）》的通知", _D(2010, 1, 1), "municipal", "深圳市人民政府", "sz"),
      _inst(31, "深圳市人民政府办公厅关于印发《深圳市政府投资项目管理办法》的通知", _D(2015, 1, 1), "municipal", "深圳市人民政府办公厅", "sz")],
     {(30, "revised_edition"): 31}),
    # date order: an earlier doc is never a successor; equal dates never pair
    ([_inst(40, "政府信息公开条例", _D(2019, 4, 3)),
      _inst(41, "政府信息公开条例（2019年修订）", _D(2019, 4, 3)),
      _inst(42, "政府信息公开条例", _D(2008, 5, 1))],
     {(42, "revised_edition"): 40}),
    # sub-national pilot -> same-locality non-pilot with the same theme
    ([_inst(50, "深圳市人民政府关于印发《深圳市知识产权保护试点工作方案》的通知", _D(2018, 1, 1), "municipal", "深圳市人民政府", "sz"),
      _inst(51, "深圳市人民政府关于印发《深圳市知识产权保护工作方案》的通知", _D(2020, 1, 1), "municipal", "深圳市人民政府", "sz")],
     {(50, "pilot_to_national"): 51}),
    # a law and its implementing regulation share a theme but are not a rename
    ([_inst(60, "中华人民共和国环境保护税法", _D(2016, 12, 25), "central", "全国人大常委会"),
      _inst(61, "中华人民共和国环境保护税法实施条例", _D(2017, 12, 25), "central", "国务院")],
     {}),
    # waves of one programme are not renames
    ([_inst(70, "住房和城乡建设部办公厅关于印发城镇老旧小区改造可复制政策机制清单（第一批）的通知", _D(2020, 12, 17), "central", "住房和城乡建设部办公厅"),
      _inst(71, "住房和城乡建设部办公厅关于印发城镇老旧小区改造可复制政策机制清单（第三批）的通知", _D(2021, 5, 28), "central", "住房和城乡建设部办公厅")],
     {}),
    # an identical title days apart on one site is a repost, not an edition
    ([_inst(80, "商务部令2004年第27号 《货物进口许可证管理办法》", _D(2005, 1, 4), "central", "商务部"),
      _inst(81, "商务部令2004年第27号 《货物进口许可证管理办法》", _D(2005, 1, 7), "central", "商务部")],
     {}),
    # sibling bureaus' parallel texts at one level are not renames (same issuer required)
    ([_inst(90, "北京市经济和信息化局关于印发《北京市经济和信息化领域行政处罚裁量基准》的通知", _D(2026, 6, 30), "provincial", "北京市经济和信息化局", "bj"),
      _inst(91, "北京市财政局关于印发《北京市财政系统行政处罚裁量基准》的通知", _D(2026, 9, 14), "provincial", "北京市财政局", "bj")],
     {}),
    # two mastheads for one text two weeks apart are copies, not a renaming
    ([_inst(97, "关于印发《中央水库移民扶持基金绩效管理暂行办法》的通知", _D(2018, 12, 31), "central", "财政部"),
      _inst(98, "财政部 水利部 国家发展改革委关于印发《中央水库移民扶持基金绩效管理暂行办法》的通知", _D(2019, 1, 15), "central", "财政部")],
     {}),
    # an annual administrative series is skipped by the title rules
    ([_inst(95, "深圳市审计局2023年工作总结及2024年工作计划", _D(2024, 12, 31), "municipal", "深圳市审计局", "sz"),
      _inst(96, "深圳市审计局2024年工作总结及2025年工作计划", _D(2025, 11, 18), "municipal", "深圳市审计局", "sz")],
     {}),
]
_DEDUP_TESTS = [
    # two candidates for one (pred, relation): higher confidence wins, then shorter lag
    ({(1, 2): (0.70, "a"), (1, 3): (0.85, "b")}, 3),
    ({(1, 2): (0.85, "a"), (1, 3): (0.85, "b")}, 2),
]


def self_test():
    fails = 0
    for a, b, same in _EDITION_TESTS:
        ea, eb = edition_core(a), edition_core(b)
        if bool(ea) and (ea == eb) != same:
            fails += 1
            print(f"XX edition_core: {ea!r} vs {eb!r} (expected same={same})")
        elif not ea:
            fails += 1
            print(f"XX edition_core({a!r}) empty")
    for a, b, same in _THEME_TESTS:
        ta, tb = theme_of(a), theme_of(b)
        if not ta or (ta == tb) != same:
            fails += 1
            print(f"XX theme_of: {ta!r} vs {tb!r} (expected same={same})")
    for s, n in _SENTENCE_TESTS:
        got = len(repeal_sentences(s))
        if got != n:
            fails += 1
            print(f"XX repeal_sentences({s[:50]!r}) = {got}, expected {n}")
    for s, exp in _PARTIAL_TESTS:
        if bool(_PARTIAL_RE.search(s)) != exp:
            fails += 1
            print(f"XX partial({s[:50]!r}) expected {exp}")
    for s, exp in _REFNAME_TESTS:
        names = ref_names(s)
        if exp not in names:
            fails += 1
            print(f"XX ref_names({s[:40]!r}) = {names!r}, expected to contain {exp!r}")
    for s, bad, good in _ENACT_TESTS:
        names = ref_names(s)
        if (bad and bad in names) or good not in names:
            fails += 1
            print(f"XX enact guard: ref_names({s[:40]!r}) = {names!r}")
    for insts_list, expected in _LINEAGE_TESTS:
        insts = {d["id"]: dict(d) for d in insts_list}
        annotate(insts)
        ed, rn = edition_pairs(insts), renamed_pairs(insts)
        pl, _ = pilot_pairs(insts, {})
        rows = assemble(insts, {}, ed, rn, pl, {})
        got = {(r["instrument_id"], r["relation"]): r["successor_id"] for r in rows}
        if got != expected:
            fails += 1
            print(f"XX lineage: {got!r}\n   expected {expected!r}")
        for r in rows:
            if insts[r["successor_id"]]["date"] <= insts[r["instrument_id"]]["date"]:
                fails += 1
                print(f"XX date order violated: {r}")
    for pairs, exp_succ in _DEDUP_TESTS:
        insts = {1: _inst(1, "甲办法", _D(2010, 1, 1)), 2: _inst(2, "甲办法乙", _D(2012, 1, 1)),
                 3: _inst(3, "甲办法丙", _D(2014, 1, 1))}
        rows = assemble(insts, {}, pairs, {}, {}, {})
        if len(rows) != 1 or rows[0]["successor_id"] != exp_succ:
            fails += 1
            print(f"XX dedup: {rows!r}, expected successor {exp_succ}")
    # stated channel end-to-end on a synthetic body
    insts = {1: _inst(1, "阳江市人民政府关于印发《阳江市政府投资项目管理暂行办法》的通知", _D(2009, 3, 1), "municipal", "阳江市人民政府", "yj"),
             2: _inst(2, "阳江市人民政府关于印发《阳江市政府投资项目管理办法》的通知", _D(2014, 6, 1), "municipal", "阳江市人民政府", "yj")}
    insts[1]["docnum"] = "阳府〔2009〕21号"
    by_title, by_docnum = defaultdict(set), defaultdict(set)
    for d in insts.values():
        for k in ref_keys(d["title"]):
            by_title[k].add(d["id"])
        if d["docnum"]:
            by_docnum[_agg_docnum(d["docnum"])].add(d["id"])
    body = "第三十条 本办法自发布之日起施行。《阳江市政府投资项目管理暂行办法》（阳府〔2009〕21号）同时废止。"
    got = stated_pairs_for(insts[2], body, insts, by_title, by_docnum)
    if set(got) != {1} or got[1][0] != CONF["stated"]:
        fails += 1
        print(f"XX stated_pairs_for: {got!r}")
    body2 = "本办法自发布之日起施行。原阳府〔2009〕21号文同时废止。"
    got = stated_pairs_for(insts[2], body2, insts, by_title, by_docnum)
    if set(got) != {1}:
        fails += 1
        print(f"XX stated_pairs_for (docnum only): {got!r}")
    # the successor never names itself
    got = stated_pairs_for(insts[1], "《阳江市政府投资项目管理暂行办法》同时废止。", insts, by_title, by_docnum)
    if got:
        fails += 1
        print(f"XX self-reference leaked: {got!r}")
    total = (len(_EDITION_TESTS) + len(_THEME_TESTS) + len(_SENTENCE_TESTS) + len(_PARTIAL_TESTS)
             + len(_REFNAME_TESTS) + len(_ENACT_TESTS)
             + len(_LINEAGE_TESTS) + len(_DEDUP_TESTS) + 3)
    print(f"self-test: {total - fails}/{total} passed")
    return fails == 0


# --------------------------------------------------------------------------- #
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--db", default=str(DB_PATH))
    ap.add_argument("--dry-run", action="store_true", help="read-only: compute, print counts + samples, no write")
    ap.add_argument("--write", action="store_true", help="rebuild instrument_succession (one transaction)")
    ap.add_argument("--force", action="store_true", help="write even if the nightly lock exists")
    ap.add_argument("--sample", type=int, default=30, help="sample rows per relation to print")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=None, help="dir for pairs.tsv + sample_<relation>.tsv (hand-check)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return 0 if self_test() else 1
    if not (args.dry_run or args.write):
        ap.error("choose --dry-run (read-only) or --write")
    if args.write and LOCK_DIR.exists() and not args.force:
        print(f"nightly lock {LOCK_DIR} exists; refusing to write (use --force)")
        return 2

    conn = connect(args.db, ro=not args.write)
    insts, rows, meta = build(conn)
    report(insts, rows, meta, args.sample, args.seed, args.out)
    if args.write:
        n, t = write(conn, rows)
        print(f"\nwrote instrument_succession: {n:,} rows in {t:.1f}s (one transaction)")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
