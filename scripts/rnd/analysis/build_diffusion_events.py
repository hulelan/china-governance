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

Anchor-identity gotcha (from both memos): the resolver scores near-duplicate
promulgations (Xinhua 受权发布, 答记者问, list-chrome mirrors, longer-titled local
lookalikes) above the canonical central text. We POOL promulgations by their EXACT
normalized 《》-core so mirrors share one anchor identity, pick the central member as
the representative (dodging the media/provincial lookalike), and attribute core-named
citation refs to the anchor even when the resolver mis-sent target_id elsewhere.
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
from extract_citations import TitleMatcher, _norm_title, _INNER_TITLE  # noqa: E402

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
ISSUANCE_RE = re.compile(r"(印发|发布|的通知|的决定|的意见|行动方案|实施方案|"
                         r"行动计划|实施意见|若干措施|工作方案|办法|规定)")
# Explainers, readouts, meeting notices, scraped list-chrome — NOT re-issuances.
NONISSUE_RE = re.compile(r"(解读|读懂|答记者问|新闻发布|发布会|新华鲜报|点击数|"
                         r"标题[:：]|主持|讲话|调研|座谈|电视电话会议|常务会议|"
                         r"党组会议|常委会|访谈|专家|引发|热议|侧记|综述)")
# Quoted "X+" cue inside “”/‘’/「」/《》 (highly distinctive, e.g. 人工智能+, 互联网+).
CUE_QUOTE_RE = re.compile(r"[“‘「『《]([^”’」』》]{2,20}\+[^”’」』》]{0,20})[”’」』》]")
TOPIC_WINDOW = 365  # days: topic_genre recency gate
TOPIC_ANCHOR_CR = 10.0  # only major campaigns propose topic_genre implementations


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


def pool_key(title):
    """Anchor-identity key: the EXACT normalized 《》-core when present (mirrors of
    one instrument share it; localized lookalikes differ), else the full norm title."""
    c = inner_core(title)
    if c:
        nc = _norm_title(c)
        if len(nc) >= STEM_MIN:
            return ("core", nc)
    return ("title", _norm_title(title))


def is_framework(genre, title):
    return genre in FW_GENRES or bool(FW_TITLE_RE.search(title or ""))


# --------------------------------------------------------------------------- #
# Load corpus                                                                  #
# --------------------------------------------------------------------------- #
def load(conn):
    site_level = dict(conn.execute("SELECT site_key, COALESCE(admin_level,'unknown') FROM sites"))
    indeg = Counter()
    for tid, n in conn.execute(
            "SELECT target_id, COUNT(*) FROM citations WHERE target_id IS NOT NULL GROUP BY target_id"):
        indeg[tid] = n
    docs = {}
    for row in conn.execute(
            f"""SELECT id, site_key, title, date_published, algo_doc_type,
                       citation_rank, topics_algo
                FROM documents
                WHERE date_published BETWEEN '{DATE_LO}' AND '{DATE_HI}'"""):
        did, sk, title, dp, genre, cr, topics = row
        docs[did] = {
            "id": did, "site": sk, "title": title or "",
            "date": _d10(dp), "genre": genre or "", "cr": cr or 0.0,
            "topics": [t for t in (topics or "").split(",") if t],
            "level": site_level.get(sk, "unknown"),
            "indeg": indeg.get(did, 0),
            "ntitle": _norm_title(title or ""),
        }
    return docs, site_level


# --------------------------------------------------------------------------- #
# Build anchors (pooled central framework instruments)                         #
# --------------------------------------------------------------------------- #
def build_anchors(docs):
    pools = defaultdict(list)
    for d in docs.values():
        pools[pool_key(d["title"])].append(d)

    anchors = {}            # anchor_id (representative) -> anchor dict
    member_to_anchor = {}   # any member doc id -> anchor_id
    core_exact = {}         # normalized 《》-core -> anchor_id (for ref attribution)

    for key, members in pools.items():
        central_fw = [m for m in members
                      if m["level"] == "central" and is_framework(m["genre"], m["title"])]
        if not central_fw:
            continue
        named = key[0] == "core"
        has_auth = any(m["cr"] >= CR_T or m["indeg"] >= DEG_T for m in members)
        if not (named or has_auth):
            continue
        # Representative = central framework member, max citation_rank, earliest date.
        rep = sorted(central_fw, key=lambda m: (-m["cr"], m["date"], m["id"]))[0]
        if not rep["date"]:
            continue
        aid = rep["id"]
        # Stem for title_reissue (from the core when named, else the full title).
        base = key[1] if named else rep["ntitle"]
        stem = genre_stem(base)
        cues = [_norm_title(c) for c in CUE_QUOTE_RE.findall(rep["title"])]
        anchors[aid] = {
            "id": aid, "date": rep["date"], "title": rep["title"],
            "ntitle": rep["ntitle"], "genre": rep["genre"], "cr": rep["cr"],
            "topics": rep["topics"], "stem": stem if len(stem) >= STEM_MIN else None,
            "cues": [c for c in cues if "+" in c],
            "members": [m["id"] for m in members],
        }
        for m in members:
            member_to_anchor.setdefault(m["id"], aid)
        if named:
            core_exact.setdefault(key[1], aid)
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
        if tid is not None and tid in member_to_anchor:
            aid = member_to_anchor[tid]
        if aid is None and ref:
            aid = core_exact.get(ref_core(ref))
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


def assemble(docs, anchors, cited, title_r, topic_g):
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
    UNIQUE(source_id, anchor_id)
);
CREATE INDEX IF NOT EXISTS idx_diffusion_anchor ON diffusion_events(anchor_id);
CREATE INDEX IF NOT EXISTS idx_diffusion_source ON diffusion_events(source_id);
CREATE INDEX IF NOT EXISTS idx_diffusion_type ON diffusion_events(match_type);
"""


def write_table(dbpath, rows):
    conn = sqlite3.connect(dbpath, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    for attempt in range(6):
        try:
            conn.executescript(DDL)
            conn.execute("DELETE FROM diffusion_events")
            conn.executemany(
                """INSERT OR REPLACE INTO diffusion_events
                   (source_id, anchor_id, match_type, lag_days, topic, source_level,
                    anchor_date, source_date, anchor_title, source_title)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""", rows)
            conn.commit()
            break
        except sqlite3.OperationalError as e:
            wait = (attempt + 1) * 10
            print(f"  DB busy ({e}); retry in {wait}s ({attempt + 1}/6)")
            time.sleep(wait)
    else:
        conn.close()
        sys.exit("ERROR: could not acquire write lock")
    n = conn.execute("SELECT COUNT(*) FROM diffusion_events").fetchone()[0]
    conn.close()
    print(f"\nWrote {n} rows to diffusion_events")


# --------------------------------------------------------------------------- #
# Report + validate                                                            #
# --------------------------------------------------------------------------- #
def report(rows, anchors, docs):
    by_type = Counter(r[2] for r in rows)
    print(f"\nTotal diffusion events: {len(rows)}")
    for t in ("citation", "title_reissue", "topic_genre"):
        print(f"  {t:<14}{by_type.get(t, 0)}")
    # Headline ranks by CONFIRMED signals only (citation + title_reissue); topic_genre
    # is a lower-confidence residual and would turn high-cr anchors into magnets.
    per_anchor = Counter()
    localities = defaultdict(set)
    for r in rows:
        if r[2] == "topic_genre":
            continue
        per_anchor[r[1]] += 1
        localities[r[1]].add(docs[r[0]]["site"])
    print("\nTop 5 most-cascaded anchors (distinct implementing localities, "
          "citation+title_reissue):")
    top = sorted(localities.items(), key=lambda kv: -len(kv[1]))[:5]
    for aid, sites in top:
        a = anchors[aid]
        print(f"  {len(sites):>3} localities | {per_anchor[aid]:>3} events | "
              f"{a['date']} | {a['title'][:52]}")


def validate(rows, anchors):
    by_anchor = defaultdict(list)
    for r in rows:
        by_anchor[r[1]].append(r)

    def cascade(label, aids):
        aids = [aid for aid in aids if aid in anchors]
        evs = [r for aid in aids for r in by_anchor.get(aid, [])]
        print(f"\n[{label}] anchors={aids}")
        if not evs:
            print("  (no events)")
            return
        lags = sorted(r[3] for r in evs if r[3] is not None)
        n = len(lags)
        med = lags[n // 2] if n else None
        print(f"  events={len(evs)}  distinct sites={len({r[5] + r[9] for r in evs})}  "
              f"median lag={med}d  min={lags[0] if lags else '-'}  max={lags[-1] if lags else '-'}")
        by_type = Counter(r[2] for r in evs)
        print(f"  by type: {dict(by_type)}")
        for r in sorted(evs, key=lambda r: r[7])[:10]:
            # r = (src, aid, mtype, lag, topic, level, adate, sdate, atitle, stitle)
            print(f"    {r[7]} {r[5]:<11} lag={r[3]:>4} {r[2]:<13} {r[9][:40]}")

    print("\n" + "=" * 78 + "\nVALIDATION\n" + "=" * 78)
    # Specific canonical anchor ids (the trade-in central family; boost; AI+).
    cascade("CONSUMPTION 以旧换新 trade-in (2024-03-13)", [900039931, 900047223, 900047235])
    cascade("CONSUMPTION 提振消费 boost (2025-03-16)", [12650974])
    cascade("AI+ 人工智能+ (2025-08-26)", [900039770])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--write", action="store_true", help="write the diffusion_events table")
    ap.add_argument("--validate", action="store_true", help="print validation cascades")
    args = ap.parse_args()

    dbpath = Path(args.db)
    if not dbpath.exists():
        sys.exit(f"DB not found: {dbpath}")
    t0 = time.time()
    conn = sqlite3.connect(f"file:{dbpath}?mode=ro", uri=True)
    docs, _ = load(conn)
    print(f"Loaded {len(docs)} docs in {time.time()-t0:.1f}s")

    anchors, member_to_anchor, core_exact = build_anchors(docs)
    print(f"Anchors: {len(anchors)} pooled central instruments "
          f"({len(member_to_anchor)} member docs, {len(core_exact)} named cores)")

    cited = match_citation(conn, docs, anchors, member_to_anchor, core_exact)
    title_r, topic_g = match_title_and_topic(docs, anchors, cited)
    conn.close()
    print(f"Raw pairs: citation={len(cited)} title_reissue={len(title_r)} topic_genre={len(topic_g)}")

    rows = assemble(docs, anchors, cited, title_r, topic_g)
    report(rows, anchors, docs)
    if args.validate:
        validate(rows, anchors)
    print(f"\nElapsed {time.time()-t0:.1f}s")

    if args.write:
        write_table(str(dbpath), rows)
    else:
        print("\n[dry run — nothing written; pass --write to build the table]")


if __name__ == "__main__":
    main()
