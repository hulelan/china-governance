#!/usr/bin/env python3
"""Successor-instrument detector — the reproducible lever behind
`docs/research/successor-detector.md` (corpus-lessons B3).

Question. The Wang & Yang replication (`docs/research/experimentation-wang-yang.md`
§3b) saw only 0.4-1.2% of central pilot themes reach a visible national instrument,
against the paper's 53.9% success rate. That proxy matched a later central title on
the pilot's *theme string*. This script builds a stronger detector and asks how much
of the gap is measurement and how much is a visibility floor.

Definitions (all from the `doc_identity` side table, no body reads):
  pilot      central promulgation (admin_level_doc='central', genre='promulgation',
             date_quality='good', 2000-2026) whose title carries
             试点|试验区|先行先试|示范区. Mirrors collapse on instrument_id.
  successor  a LATER central promulgation with NO pilot cue whose normalized title
             CORE matches the pilot's core with the pilot marker removed, or contains
             the pilot core plus a generalization cue (全面推开/全面实施/推广/在全国范围/
             扩大…范围/正式实施/办法/条例), issued by the same or a higher body
             (lead_issuer), with overlapping topics_algo. Scored; best above threshold.

Read-only: opens the DB with `?mode=ro`. Run ON the droplet (source of truth):

    .venv/bin/python3 scripts/rnd/analysis/successor_detector.py
    ... --db /root/china-governance/documents.db --repo /root/china-governance \
        --out /tmp/succ            # writes pairs.tsv / nomatch_sample.tsv / handcheck.tsv
    ... --threshold 0.62 --seed 7  # sensitivity

Imports `_norm_title` / `_title_cores_of_title` from the citation resolver so the
core logic is the one the rest of the pipeline uses.
"""
import argparse
import random
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median


def _find_repo(explicit):
    if explicit:
        return Path(explicit)
    p = Path(__file__).resolve()
    for cand in [p.parents[3] if len(p.parents) > 3 else None, Path("/root/china-governance"), Path.cwd()]:
        if cand and (cand / "analyze.py").exists():
            return cand
    return Path.cwd()


# --------------------------------------------------------------------------- #
# Title normalization                                                          #
# --------------------------------------------------------------------------- #
PILOT_RE = re.compile(r"试点|试验区|先行先试|示范区")
# Pilot markers removed to obtain the "de-piloted" core. 示范 and 试验 are dropped as
# whole words only when attached to a zone/work noun, so 示范区 -> '' but 示范 inside
# a programme name (示范工程) survives as part of the theme.
PILOT_STRIP_RE = re.compile(
    r"试点工作|试点城市|试点地区|试点单位|试点项目|试点方案|试点示范|试点|综合试验区|试验区|"
    r"先行先试|先行区|示范区|示范城市|示范园区|示范基地|示范")
GEN_CUE_RE = re.compile(
    r"全面推开|全面实施|全面推广|全面推行|推广|在全国范围|全国范围|扩大.{0,12}范围|正式实施|"
    r"复制推广|总结推广|经验推广|深化|办法|条例|规定|实施细则")
# A successor should settle an instrument, so pure 批复/函 replies to a locality are not
# candidates (they are themselves designations).
REPLY_RE = re.compile(r"批复|的函$|复函")

# Boilerplate stripped from a core before comparison. Order matters: the longer
# phrases first. This is the memo's norm_core() rebuilt on top of the resolver's
# _title_cores_of_title(), so wrapper detection is shared with the citation layer.
_BOILER = [
    r"〔\d{4}〕\d+号", r"\[\d{4}\]\d+号", r"（\d{4}）\d+号", r"第[一二三四五六七八九十\d]+批",
    r"\d{4}[-—–~～至]\d{4}年", r"\d{4}年版?", r"\d{4}[-—–]\d{4}", r"\(\d{4}\)", r"（\d{4}）",
    r"关于", r"印发", r"发布", r"公布", r"转发", r"进一步", r"做好", r"组织", r"开展", r"实施",
    r"推进", r"推动", r"加快", r"深入", r"加强", r"有关事项", r"有关问题", r"相关事项",
    r"若干", r"的通知", r"的意见", r"的决定", r"的公告", r"的通告", r"的批复", r"的函",
    r"的方案", r"的办法", r"的规定", r"通知", r"意见", r"决定", r"公告", r"方案", r"办法",
    r"规定", r"工作", r"同意", r"申报", r"认定", r"名单", r"\(试行\)", r"（试行）", r"试行",
    r"（暂行）", r"暂行", r"的", r"和", r"及", r"与", r"等",
]
_BOILER_RE = re.compile("|".join(_BOILER))
_PUNCT_RE = re.compile(r"[\s《》〈〉「」『』【】〔〕\[\]()（）“”‘’\"'、，,。．\.·・:：;；／/　—\-]")
_MASTHEAD_RE = re.compile(
    r"^(?:中共中央办公厅|中共中央|国务院办公厅|国务院|中央军委|全国人大常委会|全国人民代表大会常务委员会|"
    r"[一-鿿]{2,12}(?:部|委|局|署|行|会|院|总局|办公厅|办公室))(?:[\s、·丨]+[一-鿿]{2,14}(?:部|委|局|署|行|会|院|总局|办公厅|办公室))*")


def de_pilot(s):
    return PILOT_STRIP_RE.sub("", s or "")


def theme_core(title, norm_title, cores_of_title):
    """The policy THEME of a title: the resolver's instrument core (the 《X》 inside a
    promulgation wrapper, the 关于… body after a masthead, or the bare title), with
    issuer masthead, 文号, waves, years and genre boilerplate removed, and the pilot
    markers stripped. Returns the normalized theme string ('' if too short)."""
    t = title or ""
    cands = [c for c, f in cores_of_title(t) if f == 1]
    # prefer the shortest institutional core (the 《X》 beats the whole wrapper)
    base = min(cands, key=len) if cands else t
    base = _MASTHEAD_RE.sub("", base)
    base = _BOILER_RE.sub("", base)
    base = de_pilot(base)
    base = _PUNCT_RE.sub("", base)
    base = norm_title(base)
    return base if len(base) >= 4 else ""


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else set()


def dice(a, b):
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


# --------------------------------------------------------------------------- #
# Issuer hierarchy                                                             #
# --------------------------------------------------------------------------- #
TOP_BODIES = {"国务院", "国务院办公厅", "中共中央", "中共中央办公厅", "全国人大常委会", "全国人民代表大会",
              "全国人民代表大会常务委员会", "中央军委"}
APEX = {"中共中央", "中共中央办公厅", "全国人大常委会", "全国人民代表大会", "全国人民代表大会常务委员会"}


def issuer_rank(name):
    if not name:
        return None
    if name in APEX:
        return 3
    if name in TOP_BODIES:
        return 2
    return 1


def issuer_relation(pilot_issuer, cand_issuer):
    """'same' | 'higher' | 'unknown' | 'other'."""
    pr, cr = issuer_rank(pilot_issuer), issuer_rank(cand_issuer)
    if pr is None or cr is None:
        return "unknown"
    if pilot_issuer == cand_issuer:
        return "same"
    if cr > pr:
        return "higher"
    return "other"


# --------------------------------------------------------------------------- #
# Dates                                                                        #
# --------------------------------------------------------------------------- #
_D1 = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_D2 = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日")


def parse_date(s):
    m = _D1.match(s or "") or _D2.match(s or "")
    if not m:
        return None
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None
    if d.year < 2000 or d.year > 2026:
        return None
    return d


# --------------------------------------------------------------------------- #
# Data                                                                         #
# --------------------------------------------------------------------------- #
LOAD_SQL = """
SELECT d.id, d.title, d.date_published, d.site_key, d.document_number, d.topics_algo,
       di.lead_issuer, di.instrument_id, di.instrument_role
FROM doc_identity di JOIN documents d ON d.id = di.doc_id
WHERE di.admin_level_doc = 'central' AND di.genre = 'promulgation'
  AND di.date_quality = 'good'
"""

LONG_HORIZON_SQL = """
SELECT d.site_key FROM documents d JOIN sites s ON s.site_key = d.site_key
WHERE s.admin_level = 'central' AND length(d.date_published) >= 10
  AND d.date_published BETWEEN '2000' AND '2027'
GROUP BY d.site_key
HAVING min(substr(d.date_published,1,4)) <= '2012' AND max(substr(d.date_published,1,4)) >= '2026'
   AND count(*) >= 500
"""


def load(conn):
    rows = []
    for r in conn.execute(LOAD_SQL):
        d = parse_date(r[2])
        if not d:
            continue
        rows.append({
            "id": r[0], "title": r[1] or "", "date": d, "site": r[3], "docnum": r[4] or "",
            "topics": frozenset(t for t in (r[5] or "").split(",") if t),
            "issuer": r[6], "inst": r[7] or r[0], "role": r[8],
        })
    return rows


def collapse_instruments(rows):
    """One row per instrument_id: the canonical copy (role=canonical/unique), else the
    earliest. Topics are unioned across mirrors (a gov republish may carry topics the
    ministry copy lacks). Returns (instrument rows, n_docs)."""
    by = defaultdict(list)
    for r in rows:
        by[r["inst"]].append(r)
    out = []
    for inst, members in by.items():
        members.sort(key=lambda m: (0 if m["role"] in ("canonical", "unique") else 1, m["date"], m["id"]))
        rep = dict(members[0])
        rep["topics"] = frozenset().union(*(m["topics"] for m in members))
        rep["issuer"] = rep["issuer"] or next((m["issuer"] for m in members if m["issuer"]), None)
        rep["sites"] = sorted({m["site"] for m in members})
        rep["n_copies"] = len(members)
        out.append(rep)
    return out


# --------------------------------------------------------------------------- #
# Detector                                                                     #
# --------------------------------------------------------------------------- #
W_CORE, W_TOPIC, W_CUE, W_ISSUER, W_CITE = 0.50, 0.20, 0.15, 0.15, 0.10


def core_similarity(pcore, ccore, pbg, cbg):
    """(similarity, kind). exact 1.0; containment 0.85/0.80; else bigram Dice."""
    if pcore == ccore:
        return 1.0, "exact"
    if len(pcore) >= 5 and pcore in ccore:
        return 0.85, "contain_p"
    if len(ccore) >= 6 and ccore in pcore and len(ccore) / len(pcore) >= 0.7:
        return 0.80, "contain_c"
    return dice(pbg, cbg), "dice"


def score_pair(p, c, pcore, ccore, pbg, cbg, cites):
    sim, kind = core_similarity(pcore, ccore, pbg, cbg)
    if sim < 0.6:
        return None
    cue = 1.0 if GEN_CUE_RE.search(c["title"]) else 0.0
    if sim < 0.85 and not cue:
        return None  # a fuzzy core match needs a generalization cue
    rel = issuer_relation(p["issuer"], c["issuer"])
    if rel == "other":
        return None
    issuer = {"same": 1.0, "higher": 1.0, "unknown": 0.5}[rel]
    if p["topics"] and c["topics"]:
        topic = len(p["topics"] & c["topics"]) / len(p["topics"] | c["topics"])
        if topic == 0:
            return None  # the spec requires topic overlap when both sides carry topics
    else:
        topic = 0.5
    cite = 1.0 if (c["id"] in cites.get(p["id"], ())) or any(
        cid in cites.get(p["id"], ()) for cid in (c["id"],)) else 0.0
    lag = (c["date"] - p["date"]).days
    if lag <= 0:
        return None
    lag_pen = 0.0 if lag <= 365 * 10 else -0.05
    s = W_CORE * sim + W_TOPIC * topic + W_CUE * cue + W_ISSUER * issuer + W_CITE * cite + lag_pen
    return {"score": round(s, 3), "sim": round(sim, 3), "kind": kind, "cue": int(cue), "rel": rel,
            "topic": round(topic, 2), "cite": int(cite), "lag": lag}


def detect(pilots, cands, cores, cites, threshold):
    """For each pilot pick the best-scoring later non-pilot candidate above threshold."""
    # bigram inverted index over candidate cores so Dice is only computed on sharers
    idx = defaultdict(set)
    cbg = {}
    for c in cands:
        cc = cores[c["id"]]
        if not cc:
            continue
        bg = bigrams(cc)
        cbg[c["id"]] = bg
        for g in bg:
            idx[g].add(c["id"])
    cand_by_id = {c["id"]: c for c in cands}
    results = {}
    for p in pilots:
        pc = cores[p["id"]]
        if not pc:
            continue
        pbg = bigrams(pc)
        pool = Counter()
        for g in pbg:
            for cid in idx.get(g, ()):
                pool[cid] += 1
        best = None
        for cid, shared in pool.items():
            if shared < max(2, int(0.4 * len(pbg))):
                continue
            c = cand_by_id[cid]
            if c["date"] <= p["date"]:
                continue
            sc = score_pair(p, c, pc, cores[cid], pbg, cbg[cid], cites)
            if not sc or sc["score"] < threshold:
                continue
            key = (sc["score"], -sc["lag"])
            if best is None or key > best[0]:
                best = (key, cid, sc)
        if best:
            results[p["id"]] = (best[1], best[2])
    return results


def citation_channel(pilots, cands, cites):
    """Successors by citation only: a later central non-pilot promulgation that cites
    the pilot and carries a generalization cue. Independent of the title core."""
    cand_by_id = {c["id"]: c for c in cands}
    out = {}
    for p in pilots:
        best = None
        for cid in cites.get(p["id"], ()):
            c = cand_by_id.get(cid)
            if not c or c["date"] <= p["date"] or not GEN_CUE_RE.search(c["title"]):
                continue
            if issuer_relation(p["issuer"], c["issuer"]) == "other":
                continue
            lag = (c["date"] - p["date"]).days
            if best is None or lag < best[1]:
                best = (cid, lag)
        if best:
            out[p["id"]] = best
    return out


# --------------------------------------------------------------------------- #
# Hand-check (2026-10-06, run at threshold 0.62 on the 2026-10-06 build)        #
# --------------------------------------------------------------------------- #
# Every detected pair was read. T = the successor is the national/settled instrument
# of the pilot (de-piloted, 全面推开/推广/办法, or the de-piloted continuation of the
# same programme). P = same programme but not a rollout (a sub-instrument, the next
# wave, a partial-area launch). F = a different instrument. Keyed by pilot id so the
# precision is recomputed on every run for the pairs that are still detected.
HANDCHECK = {
    900063961: "T", 900065995: "T", 12702615: "T", 900049897: "T", 900063148: "T", 900063639: "T",
    900063622: "T", 900064295: "T", 900062716: "T", 900041260: "T", 900043947: "T", 900043948: "T",
    900044005: "T", 900049602: "P", 900050593: "T", 900050670: "T", 900055735: "T", 900111963: "T",
    900057729: "T", 900112155: "T", 900041726: "T", 900111807: "T", 900111931: "T", 900052739: "T",
    900063337: "T", 900055524: "T", 900053095: "T", 12650759: "P", 12761362: "F", 12761379: "F",
    900047448: "T", 900051038: "T", 900063466: "F", 900064611: "T", 900050566: "P", 900050945: "T",
    900052041: "T", 900055670: "P", 900057598: "T", 900052605: "T", 900055517: "T", 900064748: "T",
    900066905: "T", 12703175: "T", 900057907: "F", 900048567: "T", 900048707: "T", 900053757: "T",
    900052831: "T", 12650418: "T", 12650539: "F", 12650707: "F", 12695011: "T", 900041179: "T",
    900063677: "T", 900046274: "T", 900049571: "T", 900051302: "T", 900051500: "P", 900051986: "T",
    900053971: "T", 900056210: "T", 900056944: "P", 900057754: "F", 900051967: "F", 900054524: "T",
    900055262: "T", 900053801: "T", 900044596: "T", 900066394: "F", 12761591: "P", 900047637: "P",
    900053790: "T", 900056006: "T", 900055234: "F",
}
# Why 30 sampled no-successor pilots (seed 20261006) show none. Categories:
#   zone_wave        the designation IS the policy (自贸试验区 / 自创区 / 示范区 / 综试区
#                    batches); "scaling" = more zones in later 批复 that keep the cue
#   renamed          a national successor exists in the corpus under a renamed or
#                    absorbing instrument the core match cannot reach (海南自贸港方案,
#                    刑诉法 amendment, 国发〔2021〕7号 证照分离, 社会救助制度意见 …)
#   detector_miss    a title-preserving successor exists but was not scored (keeps the
#                    试点 word: 复制推广…试点改革举措; or a 扩大范围 variant)
#   midflight        pilot < 3y old or repeatedly extended (继续/延续实施…试点)
#   pilot_is_rollout the "pilot" was already nationwide (全面推开营改增试点)
#   never_scaled     no successor anywhere we can see (NPC 四级法院审级 trial expired;
#                    政府网站集约化试点 absorbed into routine work)
NOMATCH_WHY = {
    900057699: "zone_wave", 900040822: "zone_wave", 12737420: "never_scaled", 900049879: "detector_miss",
    900040677: "renamed", 12651491: "detector_miss", 900063862: "pilot_is_rollout", 900062302: "midflight",
    900040660: "never_scaled", 900041867: "zone_wave", 900040120: "zone_wave", 12702450: "zone_wave",
    12702685: "zone_wave", 12651586: "zone_wave", 900053073: "renamed", 900062554: "midflight",
    12747592: "renamed", 900063121: "zone_wave", 900049272: "zone_wave", 900041837: "zone_wave",
    900064619: "renamed", 900048279: "midflight", 900128067: "midflight", 12651472: "zone_wave",
    900047098: "midflight", 900046131: "midflight", 900057541: "renamed", 12760169: "zone_wave",
    900112548: "renamed", 900062730: "renamed",
}
ZONE_RE = re.compile(r"示范区|试验区|先行区|综试区|自创区")


# --------------------------------------------------------------------------- #
# Reporting                                                                    #
# --------------------------------------------------------------------------- #
def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "n/a"


def rate_block(label, pilots, found, cutoff):
    n = len(pilots)
    f = sum(1 for p in pilots if p["id"] in found)
    mature = [p for p in pilots if p["date"] <= cutoff]
    fm = sum(1 for p in mature if p["id"] in found)
    lags = [found[p["id"]][1]["lag"] if isinstance(found[p["id"]], tuple) and isinstance(found[p["id"]][1], dict)
            else found[p["id"]][1] for p in pilots if p["id"] in found]
    med = median(lags) if lags else None
    print(f"  {label:<44} pilots {n:>5}  successors {f:>4}  rate {pct(f, n):>6}  "
          f"| ex-mid-flight {fm:>4}/{len(mature):<5} {pct(fm, len(mature)):>6}  "
          f"| median lag {med if med is not None else 'n/a'} d")
    return f, fm, len(mature), med


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    ap.add_argument("--repo", default=None)
    ap.add_argument("--out", default=None, help="dir for pairs.tsv / handcheck.tsv / nomatch_sample.tsv")
    ap.add_argument("--threshold", type=float, default=0.62)
    ap.add_argument("--seed", type=int, default=20261006)
    ap.add_argument("--midflight-years", type=int, default=3)
    args = ap.parse_args()

    repo = _find_repo(args.repo)
    sys.path.insert(0, str(repo))
    sys.path.insert(0, str(repo / "scripts" / "rnd" / "citations"))
    from extract_citations import _norm_title, _title_cores_of_title  # noqa: E402

    db = Path(args.db) if args.db else repo / "documents.db"
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rng = random.Random(args.seed)

    rows = load(conn)
    insts = collapse_instruments(rows)
    long_sites = {r[0] for r in conn.execute(LONG_HORIZON_SQL)}
    # a handful of docs carry future dates; cap the corpus horizon at today
    max_date = min(max(r["date"] for r in rows), date.today())
    cutoff = max_date - timedelta(days=365 * args.midflight_years)

    pilots_docs = [r for r in rows if PILOT_RE.search(r["title"])]
    pilots = [r for r in insts if PILOT_RE.search(r["title"])]
    cands = [r for r in insts if not PILOT_RE.search(r["title"]) and not REPLY_RE.search(r["title"])]
    cores = {r["id"]: theme_core(r["title"], _norm_title, _title_cores_of_title) for r in insts}

    # citations among central promulgations: pilot -> set(citing later docs), pooled on instrument
    doc2inst = {r["id"]: r["inst"] for r in rows}
    inst_rep = {r["inst"]: r["id"] for r in insts}
    cites = defaultdict(set)
    q = "SELECT source_id, target_id FROM citations WHERE target_id IS NOT NULL"
    for s, t in conn.execute(q):
        if t in doc2inst and s in doc2inst:
            cites[inst_rep[doc2inst[t]]].add(inst_rep[doc2inst[s]])

    print("=" * 100)
    print("SUCCESSOR-INSTRUMENT DETECTOR  (read-only; db =", db, ")")
    print("=" * 100)
    print(f"central promulgations (doc_identity, date_quality=good, 2000-2026): {len(rows):,} docs "
          f"-> {len(insts):,} instruments (instrument_id collapse)")
    print(f"pilot cue in title (试点|试验区|先行先试|示范区): {len(pilots_docs):,} docs -> {len(pilots):,} instruments "
          f"(memo's title-family set: 1,592 docs / 1,296 themes)")
    print(f"pilots with a usable theme core (>=4 chars): {sum(1 for p in pilots if cores[p['id']]):,}")
    print(f"successor candidates (later central non-pilot, non-reply promulgations): {len(cands):,}")
    print(f"long-horizon central sites (min<=2012, max>=2026, >=500 docs): {sorted(long_sites)}")
    print(f"corpus max date {max_date}; mid-flight cutoff (pilot < {args.midflight_years}y old): {cutoff}")

    found = detect(pilots, cands, cores, cites, args.threshold)
    strict = {k: v for k, v in found.items() if v[1]["kind"] in ("exact", "contain_p", "contain_c")}
    cite_only = citation_channel(pilots, cands, cites)
    union = dict(found)
    for k, v in cite_only.items():
        union.setdefault(k, (v[0], {"lag": v[1], "kind": "citation", "score": None}))

    print("\n--- Scale rates (pilot instruments with a national successor) ---")
    print(f"  Wang & Yang: 53.9% of experiments scale; mean duration 2.25 years (~820 d)")
    print(f"  Memo §3b title-family proxy: 0.4-1.2% (5-16 of 1,296 themes), median lag 738-1,070 d")
    rate_block(f"detector, all pilots (threshold {args.threshold})", pilots, found, cutoff)
    rate_block("  strict core-match only (exact/containment)", pilots, strict, cutoff)
    rate_block("  + citation channel (cites pilot + gen cue)", pilots, union, cutoff)
    trials = [p for p in pilots if "试点" in p["title"] and not ZONE_RE.search(p["title"])]
    rate_block("试点-cued trials only (no zone names)", trials, found, cutoff)
    rate_block("  trials, strict core-match only", trials, strict, cutoff)
    rate_block("  trials, + citation channel", trials, union, cutoff)
    lp = [p for p in pilots if p["site"] in long_sites]
    rate_block("long-horizon central sites only", lp, found, cutoff)
    rate_block("  strict, long-horizon", lp, strict, cutoff)
    for y0, y1 in [(2000, 2009), (2010, 2015), (2016, 2019), (2020, 2023)]:
        sub = [p for p in pilots if y0 <= p["date"].year <= y1]
        rate_block(f"pilots dated {y0}-{y1}", sub, found, cutoff)

    kinds = Counter(v[1]["kind"] for v in found.values())
    print("\n  match kinds:", dict(kinds), "| with gen cue:", sum(v[1]["cue"] for v in found.values()),
          "| citing the pilot:", sum(v[1]["cite"] for v in found.values()),
          "| issuer rel:", dict(Counter(v[1]["rel"] for v in found.values())))
    lags = sorted(v[1]["lag"] for v in found.values())
    if lags:
        print(f"  lag quartiles (d): p25 {lags[len(lags)//4]}  median {median(lags)}  p75 {lags[3*len(lags)//4]}  "
              f"| <=820 d (their mean duration): {pct(sum(1 for l in lags if l <= 820), len(lags))}")

    # thresholds sensitivity
    print("\n--- Threshold sensitivity (all pilots) ---")
    for th in (0.55, 0.60, 0.62, 0.65, 0.70, 0.75):
        f = detect(pilots, cands, cores, cites, th)
        print(f"  threshold {th:.2f}: successors {len(f):>4}  rate {pct(len(f), len(pilots))}")

    # by issuer / topic
    print("\n--- Scale rate by pilot lead_issuer (>=15 pilots) ---")
    by_iss = defaultdict(list)
    for p in pilots:
        by_iss[p["issuer"] or "(none)"].append(p)
    for iss, ps in sorted(by_iss.items(), key=lambda kv: -len(kv[1])):
        if len(ps) < 15:
            continue
        f = sum(1 for p in ps if p["id"] in found)
        print(f"  {iss:<16} pilots {len(ps):>4}  successors {f:>3}  rate {pct(f, len(ps))}")
    print("\n--- Scale rate by pilot topic (topics_algo, >=20 pilots) ---")
    by_top = defaultdict(list)
    for p in pilots:
        for t in (p["topics"] or {"(none)"}):
            by_top[t].append(p)
    for t, ps in sorted(by_top.items(), key=lambda kv: -len(kv[1])):
        if len(ps) < 20:
            continue
        f = sum(1 for p in ps if p["id"] in found)
        print(f"  {t:<16} pilots {len(ps):>4}  successors {f:>3}  rate {pct(f, len(ps))}")

    # hand-check precision (pairs still detected that carry a verdict)
    print("\n--- Hand-check precision (every detected pair read; verdicts in HANDCHECK) ---")
    ver = Counter(HANDCHECK.get(pid, "?") for pid in found)
    n_v = sum(v for k, v in ver.items() if k != "?")
    if n_v:
        t, p_ = ver.get("T", 0), ver.get("P", 0)
        print(f"  checked {n_v} of {len(found)} pairs: T {t}  P {p_}  F {ver.get('F', 0)}  "
              f"| precision strict (T) {pct(t, n_v)}  lenient (T+P) {pct(t + p_, n_v)}  "
              f"| unverified {ver.get('?', 0)}")
        by_kind = defaultdict(Counter)
        for pid, (cid, sc) in found.items():
            by_kind[sc["kind"]][HANDCHECK.get(pid, "?")] += 1
        for k, c in by_kind.items():
            tot = sum(v for kk, v in c.items() if kk != "?")
            print(f"    kind {k:<10} T {c.get('T', 0):>3}  P {c.get('P', 0):>3}  F {c.get('F', 0):>3}  "
                  f"strict precision {pct(c.get('T', 0), tot)}")
        prec = t / n_v
        prec_l = (t + p_) / n_v
        n_mature = sum(1 for p in pilots if p["date"] <= cutoff)
        f_mature = sum(1 for p in pilots if p["date"] <= cutoff and p["id"] in found)
        print(f"  precision-adjusted scale rate: all {pct(len(found) * prec, len(pilots))} (strict) / "
              f"{pct(len(found) * prec_l, len(pilots))} (lenient); ex-mid-flight "
              f"{pct(f_mature * prec, n_mature)} / {pct(f_mature * prec_l, n_mature)}")

    # no-successor hand sample: why
    whys = Counter(NOMATCH_WHY.values())
    print("\n--- No-successor hand sample (30 pilots, seed 20261006): why ---")
    for k, v in whys.most_common():
        print(f"  {k:<16} {v:>2}  {pct(v, len(NOMATCH_WHY))}")
    sub = {k: v for k, v in NOMATCH_WHY.items() if v not in ("zone_wave", "midflight")}
    exists = sum(1 for v in sub.values() if v in ("renamed", "detector_miss"))
    print(f"  among substantive, mature no-successor pilots ({len(sub)}): a successor EXISTS in the corpus for "
          f"{exists} ({pct(exists, len(sub))}); pilot_is_rollout {sum(1 for v in sub.values() if v == 'pilot_is_rollout')}; "
          f"never_scaled {sum(1 for v in sub.values() if v == 'never_scaled')}")

    # no-successor diagnostics (automatic part): pilot-core found in ANY later central doc
    # (incl. news/explainer/other genres) = "the theme lives on but not as a promulgation"
    print("\n--- No-successor pilots: automatic triage ---")
    nomatch = [p for p in pilots if p["id"] not in found and cores[p["id"]]]
    mid = [p for p in nomatch if p["date"] > cutoff]
    print(f"  no successor: {len(nomatch)}  of which mid-flight (< {args.midflight_years}y): {len(mid)}")
    zone = [p for p in nomatch if re.search(r"示范区|试验区|先行区", p["title"]) and not re.search(r"试点", p["title"])]
    print(f"  zone/area designations (示范区/试验区 without 试点), standing names not trials: {len(zone)}")
    reply = [p for p in nomatch if re.search(r"批复|同意", p["title"])]
    print(f"  approval replies (批复/同意…) = a locality-specific designation: {len(reply)}")
    later_any = 0
    cand_cores = [(c["id"], cores[c["id"]], c["date"]) for c in insts if cores[c["id"]]]
    for p in nomatch:
        pc = cores[p["id"]]
        if any(pc in cc and d > p["date"] for _, cc, d in cand_cores if len(pc) >= 5):
            later_any += 1
    print(f"  theme core reappears in ANY later central promulgation title (incl. pilots/replies): {later_any}")

    # outputs for hand-check
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        cand_by_id = {c["id"]: c for c in cands}
        with open(out / "pairs.tsv", "w") as fh:
            fh.write("pilot_id\tpilot_date\tpilot_issuer\tpilot_title\tsucc_id\tsucc_date\tsucc_issuer\tsucc_title\t"
                     "score\tsim\tkind\tcue\trel\ttopic\tcite\tlag\tpilot_core\tsucc_core\n")
            for pid, (cid, sc) in sorted(found.items(), key=lambda kv: -kv[1][1]["score"]):
                p = next(x for x in pilots if x["id"] == pid)
                c = cand_by_id[cid]
                fh.write("\t".join(str(x) for x in [
                    pid, p["date"], p["issuer"], p["title"], cid, c["date"], c["issuer"], c["title"],
                    sc["score"], sc["sim"], sc["kind"], sc["cue"], sc["rel"], sc["topic"], sc["cite"], sc["lag"],
                    cores[pid], cores[cid]]) + "\n")
        hc = rng.sample(sorted(found.items()), min(40, len(found)))
        with open(out / "handcheck.tsv", "w") as fh:
            fh.write("n\tpilot_id\tpilot_date\tpilot_title\tsucc_id\tsucc_date\tsucc_title\tscore\tkind\tlag\tverdict\n")
            for i, (pid, (cid, sc)) in enumerate(hc, 1):
                p = next(x for x in pilots if x["id"] == pid)
                c = cand_by_id[cid]
                fh.write("\t".join(str(x) for x in [i, pid, p["date"], p["title"], cid, c["date"], c["title"],
                                                     sc["score"], sc["kind"], sc["lag"], ""]) + "\n")
        nm = rng.sample(nomatch, min(30, len(nomatch)))
        with open(out / "nomatch_sample.tsv", "w") as fh:
            fh.write("n\tpilot_id\tdate\tissuer\tsite\ttitle\tcore\tmidflight\tloose_later_titles\n")
            for i, p in enumerate(nm, 1):
                pc = cores[p["id"]]
                # loose probe: later central instruments sharing >=50% of the pilot core's bigrams
                pbg = bigrams(pc)
                loose = []
                for c in insts:
                    if c["date"] <= p["date"] or c["id"] == p["id"]:
                        continue
                    cc = cores[c["id"]]
                    if cc and dice(pbg, bigrams(cc)) >= 0.5:
                        loose.append(f"{c['date']} {c['title']}")
                fh.write("\t".join(str(x) for x in [i, p["id"], p["date"], p["issuer"], p["site"], p["title"], pc,
                                                     int(p["date"] > cutoff), " || ".join(loose[:4])]) + "\n")
        print(f"\nwrote {out}/pairs.tsv ({len(found)}), handcheck.tsv ({len(hc)}), nomatch_sample.tsv ({len(nm)})")


if __name__ == "__main__":
    main()
