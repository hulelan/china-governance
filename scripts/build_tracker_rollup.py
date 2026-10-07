"""Precompute `tracker_weekly` — the per-topic / per-ISO-week / per-level rollup
behind the daily policy tracker (step 2 of docs/research/daily-tracker-concept.md).

Same pattern as `build_site_stats.py`: a small table rebuilt nightly in the clean
write-window (daily_sync.sh Phase 2c, after citations/scores/topics and the
diffusion-events auto-matcher, before the Phase 3 checkpoint) so the tracker view
reads a few indexed rows instead of scanning `documents` × `topics_algo` cold.

One row per (topic, iso_week, admin_level):
  new_docs                 docs published that ISO week at that level carrying the
                           topic (`topics_algo` is a comma-separated multi-label;
                           each tag counts once, and every doc also counts under
                           topic='all').
  cascade_events           confirmed IMPLEMENTING diffusion events (match_type citation
                           or title_reissue AND source_implementing=1 — the source is
                           a policy instrument, not a readout/explainer/news item)
                           whose SOURCE doc was published that week at that level,
                           under every topic of the event's ANCHOR (the campaign
                           defines the topic; `diffusion_events.topic` only stores
                           the anchor's first tag) — and under 'all'.
  cascade_events_mentions  confirmed events whose source merely MENTIONS the anchor
                           (source_implementing=0: 党组会议 readouts, 解读, speech
                           reposts…). Kept as a secondary signal, never a cascade.
  cascade_events_lowconf   the same for match_type topic_genre (probable, unconfirmed).
  cascade_events_prov      confirmed implementing events whose anchor is a PROVINCIAL
                           instrument (anchor_level='provincial', the province→city
                           hop of fidelity-provincial.md). Provincial mentions and
                           topic_genre are not rolled up. cascade_events / _mentions /
                           _lowconf stay central-anchor only.

  n_sites / top_site_share / top_site   (2026-10-07, additive — appended at the end)
                           site diversity of that cell's `cascade_events`: distinct
                           source `documents.site_key` among them, the modal site's
                           share of them, and that site's key. policy-tempo.md §3
                           found the pooled weekly bursts are single-portal archive
                           batches (Guangzhou 51/83 in 2023-W01, Shenzhen 57/66 in
                           2020-W11, lvliang+npc on 生态环境法典 in 2026-W33), all with
                           date_quality='good', so a raw burst can be one site's
                           upload rather than tempo. The tracker turns these into a
                           per-week `diverse` flag (web/services/tracker.py) and
                           tags the rest "single-source"; counts are unchanged.

  n_anchors / top_anchor_share / top_anchor   (2026-10-07, additive — after the site
                           columns) the complementary ANCHOR concentration of that
                           cell's `cascade_events`: distinct anchor instruments among
                           them, the modal instrument's share, and that instrument's
                           id. Anchors are pooled by `doc_identity.instrument_id`
                           (mirror promulgations of one text are one instrument;
                           falls back to anchor_id when the table/column is absent).
                           2026-W33 passes the site gate (75 events, 26 sites) but is
                           生态环境法典 echoed 25 times — one law's arrival, not tempo.
                           The tracker tags such weeks "single-instrument"
                           (is_single_instrument); counts are unchanged.

Bounded to date_published 2018-01-01..2026-12-31 — the tracker is about recent
weeks, and this keeps the table small and the rebuild a few seconds.
Idempotent: CREATE IF NOT EXISTS + DELETE + INSERT.

    python3 scripts/build_tracker_rollup.py [--db documents.db] [--stats]
    python3 scripts/build_tracker_rollup.py --dry-run   # read-only: compute in memory,
        # print both gates' distributions, the weeks each flags per topic, the known
        # batch weeks (the two single-portal weeks must flag single-source, 2026-W33
        # must flag single-instrument) and the top-20 burst survivors per topic
"""
import argparse
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "documents.db"
sys.path.insert(0, str(ROOT))
from web.services.tracker import (  # noqa: E402  (pure functions, no app deps)
    DIVERSE_MIN_EVENTS, DIVERSE_MIN_SITES, DIVERSE_MAX_SHARE, is_diverse, row_diversity,
    SINGLE_INSTR_MIN_SHARE, SINGLE_INSTR_MIN_TOP, is_single_instrument, row_instrument)

DATE_LO, DATE_HI = "2018-01-01", "2026-12-31"
ALL = "all"
CONFIRMED = {"citation", "title_reissue"}
LOWCONF = {"topic_genre"}

DDL = """
CREATE TABLE IF NOT EXISTS tracker_weekly (
    topic                  TEXT NOT NULL,
    iso_week               TEXT NOT NULL,   -- 'YYYY-Www' (ISO 8601 week)
    admin_level            TEXT NOT NULL,
    week_start             TEXT NOT NULL,   -- Monday of that ISO week, 'YYYY-MM-DD'
    new_docs               INTEGER NOT NULL DEFAULT 0,
    cascade_events         INTEGER NOT NULL DEFAULT 0,
    cascade_events_lowconf INTEGER NOT NULL DEFAULT 0,
    cascade_events_prov    INTEGER NOT NULL DEFAULT 0,
    cascade_events_mentions INTEGER NOT NULL DEFAULT 0,
    n_sites                INTEGER NOT NULL DEFAULT 0,   -- distinct source sites among cascade_events
    top_site_share         REAL    NOT NULL DEFAULT 0,   -- modal site's events / cascade_events
    top_site               TEXT    NOT NULL DEFAULT '',  -- that modal site_key
    n_anchors              INTEGER NOT NULL DEFAULT 0,   -- distinct anchor instruments among cascade_events
    top_anchor_share       REAL    NOT NULL DEFAULT 0,   -- modal instrument's events / cascade_events
    top_anchor             INTEGER NOT NULL DEFAULT 0,   -- that instrument_id (= canonical doc id)
    PRIMARY KEY (topic, iso_week, admin_level)
);
CREATE INDEX IF NOT EXISTS idx_tracker_weekly_topic_week ON tracker_weekly(topic, iso_week);
"""
MIGRATE = {
    "cascade_events_prov":
        "ALTER TABLE tracker_weekly ADD COLUMN cascade_events_prov INTEGER NOT NULL DEFAULT 0;",
    "cascade_events_mentions":
        "ALTER TABLE tracker_weekly ADD COLUMN cascade_events_mentions INTEGER NOT NULL DEFAULT 0;",
    "n_sites":
        "ALTER TABLE tracker_weekly ADD COLUMN n_sites INTEGER NOT NULL DEFAULT 0;",
    "top_site_share":
        "ALTER TABLE tracker_weekly ADD COLUMN top_site_share REAL NOT NULL DEFAULT 0;",
    "top_site":
        "ALTER TABLE tracker_weekly ADD COLUMN top_site TEXT NOT NULL DEFAULT '';",
    "n_anchors":
        "ALTER TABLE tracker_weekly ADD COLUMN n_anchors INTEGER NOT NULL DEFAULT 0;",
    "top_anchor_share":
        "ALTER TABLE tracker_weekly ADD COLUMN top_anchor_share REAL NOT NULL DEFAULT 0;",
    "top_anchor":
        "ALTER TABLE tracker_weekly ADD COLUMN top_anchor INTEGER NOT NULL DEFAULT 0;",
}
# agg column slots
NEW, CAS, LOW, PROV, MENT = range(5)


def _modal(counts, empty_key):
    """(n_keys, modal share, modal key) of a Counter; ties -> highest key."""
    if not counts:
        return 0, 0.0, empty_key
    top_key, top_n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    total = sum(counts.values())
    return len(counts), round(top_n / total, 4), top_key


def site_diversity(site_counts) -> tuple:
    """(n_sites, top_site_share, top_site) for one cell's implementing-cascade
    site counter ({site_key: events}). Empty counter -> (0, 0.0, '')."""
    return _modal(site_counts, "")


def anchor_diversity(anchor_counts) -> tuple:
    """(n_anchors, top_anchor_share, top_anchor) for one cell's implementing-cascade
    anchor counter ({instrument_id: events}). Empty counter -> (0, 0.0, 0)."""
    return _modal(anchor_counts, 0)


def iso_week(d10: str):
    """'YYYY-MM-DD' -> ('YYYY-Www', monday 'YYYY-MM-DD'), or None if unparseable."""
    try:
        y, m, d = int(d10[0:4]), int(d10[5:7]), int(d10[8:10])
        dt = date(y, m, d)
    except (ValueError, TypeError):
        return None
    iy, iw, iwd = dt.isocalendar()
    monday = date.fromordinal(dt.toordinal() - (iwd - 1))
    return f"{iy}-W{iw:02d}", monday.isoformat()


def split_topics(s):
    return [t for t in (s or "").split(",") if t]


def compute(conn) -> dict:
    """Aggregate documents + diffusion_events into memory (read-only).

    Returns {agg, sites, pooled_sites, anchors, pooled_anchors, anchor_titles, weeks,
             n_docs, n_ev}:
      agg            (topic, iso_week, level) -> [new, cas, low, prov, ment]
      sites          (topic, iso_week, level) -> Counter{site_key: implementing cascade events}
      pooled_sites   (topic, iso_week)        -> the same Counter summed over levels
                     (exact pooled diversity — used by --dry-run to check the
                     service's per-level merge, which can only approximate it)
      anchors        (topic, iso_week, level) -> Counter{instrument_id: implementing events}
      pooled_anchors (topic, iso_week)        -> the same summed over levels
      anchor_titles  instrument_id -> an anchor title (for the dry-run report only)
    """
    ev_cols = {r[1] for r in conn.execute("PRAGMA table_info(diffusion_events)")}
    level_expr = ("COALESCE(e.anchor_level,'central')" if "anchor_level" in ev_cols
                  else "'central'")
    # Pre-flag tables: every confirmed event counts as implementing (old behaviour).
    impl_expr = ("COALESCE(e.source_implementing,1)" if "source_implementing" in ev_cols
                 else "1")
    # Anchor pooling: mirror promulgations of one text share an instrument_id
    # (doc_identity, 2026-10-06). Missing table/column -> each anchor is its own.
    inst_of: dict = {}
    if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='doc_identity'"
                    ).fetchone():
        id_cols = {r[1] for r in conn.execute("PRAGMA table_info(doc_identity)")}
        if "instrument_id" in id_cols:
            inst_of = dict(conn.execute(
                "SELECT doc_id, instrument_id FROM doc_identity WHERE instrument_id IS NOT NULL"))

    site_level = dict(conn.execute(
        "SELECT site_key, COALESCE(admin_level,'unknown') FROM sites"))
    week_cache: dict[str, tuple] = {}

    def wk(d10):
        if d10 not in week_cache:
            week_cache[d10] = iso_week(d10)
        return week_cache[d10]

    # (topic, iso_week, level) -> [new_docs, cascade, cascade_lowconf, cascade_prov, mentions]
    agg: dict[tuple, list] = defaultdict(lambda: [0, 0, 0, 0, 0])
    sites: dict[tuple, Counter] = defaultdict(Counter)
    pooled_sites: dict[tuple, Counter] = defaultdict(Counter)
    anchors: dict[tuple, Counter] = defaultdict(Counter)
    pooled_anchors: dict[tuple, Counter] = defaultdict(Counter)
    anchor_titles: dict[int, str] = {}
    weeks: dict[str, str] = {}  # iso_week -> week_start

    # --- new_docs: single sequential scan, small columns only (no body) ---
    # substr: date_published is mixed 'YYYY-MM-DD' / '... HH:MM[:SS]'.
    n_docs = 0
    for site_key, d10, topics in conn.execute(
            "SELECT site_key, substr(date_published,1,10), topics_algo "
            "FROM documents WHERE substr(date_published,1,10) BETWEEN ? AND ?",
            (DATE_LO, DATE_HI)):
        w = wk(d10)
        if w is None:
            continue
        iw, monday = w
        weeks[iw] = monday
        level = site_level.get(site_key, "unknown")
        n_docs += 1
        agg[(ALL, iw, level)][NEW] += 1
        for t in set(split_topics(topics)):
            agg[(t, iw, level)][NEW] += 1

    # --- cascade events: anchor's full topic set (fallback: stored topic) ---
    # s.site_key = the SOURCE doc's portal, for the per-cell site-diversity columns.
    n_ev = 0
    for (mtype, d10, level, ev_topic, anchor_topics, alevel, impl, src_site,
         anchor_id, anchor_title) in conn.execute(
            "SELECT e.match_type, substr(e.source_date,1,10), "
            f"       COALESCE(e.source_level,'unknown'), e.topic, d.topics_algo, {level_expr}, "
            f"       {impl_expr}, COALESCE(s.site_key,''), e.anchor_id, e.anchor_title "
            "FROM diffusion_events e LEFT JOIN documents d ON d.id = e.anchor_id "
            "                        LEFT JOIN documents s ON s.id = e.source_id "
            "WHERE substr(e.source_date,1,10) BETWEEN ? AND ?",
            (DATE_LO, DATE_HI)):
        if alevel == "provincial":
            if mtype not in CONFIRMED or not impl:
                continue  # provincial topic_genre / mentions are not rolled up (keep it minimal)
            col = PROV
        elif mtype in CONFIRMED:
            col = CAS if impl else MENT
        elif mtype in LOWCONF:
            col = LOW
        else:
            continue
        w = wk(d10)
        if w is None:
            continue
        iw, monday = w
        weeks[iw] = monday
        n_ev += 1
        topics = set(split_topics(anchor_topics)) or set(split_topics(ev_topic))
        inst = inst_of.get(anchor_id, anchor_id) or 0
        if col == CAS:
            anchor_titles.setdefault(inst, anchor_title or "")
        for t in topics | {ALL}:
            agg[(t, iw, level)][col] += 1
            if col == CAS:
                sites[(t, iw, level)][src_site] += 1
                pooled_sites[(t, iw)][src_site] += 1
                anchors[(t, iw, level)][inst] += 1
                pooled_anchors[(t, iw)][inst] += 1

    return {"agg": agg, "sites": sites, "pooled_sites": pooled_sites,
            "anchors": anchors, "pooled_anchors": pooled_anchors,
            "anchor_titles": anchor_titles, "weeks": weeks,
            "n_docs": n_docs, "n_ev": n_ev}


def build(db_path: Path) -> tuple:
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(DDL)
        tw_cols = {r[1] for r in conn.execute("PRAGMA table_info(tracker_weekly)")}
        for col, ddl in MIGRATE.items():
            if col not in tw_cols:
                conn.executescript(ddl)

        r = compute(conn)
        agg, sites, anchors, weeks = r["agg"], r["sites"], r["anchors"], r["weeks"]
        rows_out = []
        for (t, iw, lvl), v in agg.items():
            n_sites, share, top = site_diversity(sites.get((t, iw, lvl)))
            n_anc, a_share, a_top = anchor_diversity(anchors.get((t, iw, lvl)))
            rows_out.append((t, iw, lvl, weeks[iw], v[NEW], v[CAS], v[LOW], v[PROV], v[MENT],
                             n_sites, share, top, n_anc, a_share, a_top))

        conn.execute("DELETE FROM tracker_weekly")
        conn.executemany(
            "INSERT INTO tracker_weekly(topic, iso_week, admin_level, week_start, "
            "new_docs, cascade_events, cascade_events_lowconf, cascade_events_prov, "
            "cascade_events_mentions, n_sites, top_site_share, top_site, "
            "n_anchors, top_anchor_share, top_anchor) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows_out)
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        rows = conn.execute("SELECT COUNT(*) FROM tracker_weekly").fetchone()[0]
        return rows, r["n_docs"], r["n_ev"]
    finally:
        conn.close()


# The three batch weeks policy-tempo.md §3 identified: (topic, iso_week, expected
# modal site, must_flag_site, expected modal-instrument title fragment,
# must_flag_instrument). The two SINGLE-portal weeks must be flagged single-source
# (--dry-run exits 1 otherwise). The third is a different animal — "lvliang 15 +
# npc 14 on one law" out of 75 events from 26 sites (modal site share 0.20 on
# 2026-10-07): a one-ANCHOR concentration spread over many portals, which a
# modal-site gate does not and should not catch (flagging it would need share
# <= 0.19, i.e. most weeks). It is the anchor gate's case: 生态环境法典 = 25/75
# (0.333), and --dry-run exits 1 if the anchor gate does NOT flag it.
KNOWN_BATCH_WEEKS = [
    (ALL, "2023-W01", "gz", True, None, False),       # Guangzhou 51/83 events, week of 2023-01-02
    (ALL, "2020-W11", "sz", True, None, False),       # Shenzhen 57/66, week of 2020-03-09
    (ALL, "2026-W33", None, False, "生态环境法典", True),  # one law echoed 25/75, week of 2026-08-10
]
TOP_BURSTS = 20


def dry_run(db_path: Path):
    """Read-only: compute into memory and print what both gates would do."""
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=30)
    try:
        conn.execute("PRAGMA busy_timeout=30000")
        t0 = time.time()
        r = compute(conn)
    finally:
        conn.close()
    agg, sites, pooled = r["agg"], r["sites"], r["pooled_sites"]
    anchors, pooled_a, titles = r["anchors"], r["pooled_anchors"], r["anchor_titles"]
    print(f"computed in memory: {len(agg):,} cells from {r['n_docs']:,} docs + "
          f"{r['n_ev']:,} events, {time.time()-t0:.1f}s (nothing written)")
    print(f"site gate: cascade_events >= {DIVERSE_MIN_EVENTS} AND n_sites >= {DIVERSE_MIN_SITES} "
          f"AND top_site_share <= {DIVERSE_MAX_SHARE}")
    print(f"instrument gate: cascade_events >= {DIVERSE_MIN_EVENTS} AND top_anchor_share > "
          f"{SINGLE_INSTR_MIN_SHARE} AND modal instrument events >= {SINGLE_INSTR_MIN_TOP}")

    # pooled per (topic, week): exact diversity from the pooled counters
    pooled_cas = Counter()
    for (t, iw, lvl), v in agg.items():
        pooled_cas[(t, iw)] += v[CAS]
    exact = {k: site_diversity(c) for k, c in pooled.items()}
    exact_a = {k: anchor_diversity(c) for k, c in pooled_a.items()}

    def ttl(inst):
        return " ".join((titles.get(inst) or "").split())[:36]

    # --- 1. distribution over weeks with >= DIVERSE_MIN_EVENTS pooled events (topic='all')
    print(f"\n[1] distribution, topic='all', weeks with >= {DIVERSE_MIN_EVENTS} events")
    allw = [(iw, pooled_cas[(ALL, iw)], exact[(ALL, iw)], exact_a[(ALL, iw)])
            for (t, iw) in pooled if t == ALL and pooled_cas[(ALL, iw)] >= DIVERSE_MIN_EVENTS]
    print(f"    weeks: {len(allw)}")
    for lo, hi in [(0, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7), (.7, .8), (.8, 1.01)]:
        n = sum(1 for _, _, d, _ in allw if lo <= d[1] < hi)
        print(f"    top_site_share [{lo:.1f},{hi:.1f}): {n:4d}")
    for ns in range(1, 8):
        n = sum(1 for _, _, d, _ in allw if d[0] == ns)
        print(f"    n_sites == {ns}: {n:4d}")
    print(f"    n_sites >= 8: {sum(1 for _, _, d, _ in allw if d[0] >= 8):4d}")
    print("    -- anchor concentration (instrument_id-pooled) --")
    for lo, hi in [(0, .2), (.2, .3), (.3, .4), (.4, .5), (.5, .6), (.6, .7), (.7, 1.01)]:
        n = sum(1 for _, _, _, a in allw if lo <= a[1] < hi)
        print(f"    top_anchor_share [{lo:.1f},{hi:.1f}): {n:4d}")
    above = [(iw, cas, a) for iw, cas, _, a in allw if a[1] > SINGLE_INSTR_MIN_SHARE]
    small = sum(1 for _, cas, a in above if round(a[1] * cas) < SINGLE_INSTR_MIN_TOP)
    print(f"    weeks with top_anchor_share > {SINGLE_INSTR_MIN_SHARE}: {len(above)}, of which "
          f"{small} have < {SINGLE_INSTR_MIN_TOP} events on the modal instrument (not flagged)")
    big = sorted(allw, key=lambda x: -x[1])[:TOP_BURSTS]
    print(f"    top-{TOP_BURSTS} weeks by events (events | n_sites share top_site diverse | "
          f"n_anchors share single_instrument top_anchor):")
    for iw, cas, (ns, sh, top), (na, ash, atop) in big:
        print(f"      {iw} {cas:4d} | {ns:3d} {sh:.2f} {top:<12} {str(is_diverse(cas, ns, sh)):<5} | "
              f"{na:3d} {ash:.2f} {str(is_single_instrument(cas, na, ash)):<5} {ttl(atop)}")

    # --- 2. weeks flagged by topic (pooled, exact)
    print(f"\n[2] weeks flagged by topic, among weeks with >= {DIVERSE_MIN_EVENTS} events "
          f"(site gate | instrument gate)")
    by_topic = defaultdict(list)
    for (t, iw), cas in pooled_cas.items():
        if cas >= DIVERSE_MIN_EVENTS:
            by_topic[t].append((iw, cas, exact[(t, iw)], exact_a[(t, iw)]))
    print(f"    {'topic':<16}{'weeks':>6} | {'1-site':>7}{'%':>5}  top-{TOP_BURSTS} surv"
          f" | {'1-inst':>7}{'%':>5}  top-{TOP_BURSTS} flagged")
    for t in sorted(by_topic, key=lambda x: (x != ALL, x.lower())):
        ws = by_topic[t]
        flagged = sum(1 for _, cas, (ns, sh, _), _ in ws if is_diverse(cas, ns, sh) is False)
        top = sorted(ws, key=lambda x: -x[1])[:TOP_BURSTS]
        surv = sum(1 for _, cas, (ns, sh, _), _ in top if is_diverse(cas, ns, sh))
        fl_a = sum(1 for _, cas, _, (na, ash, _) in ws if is_single_instrument(cas, na, ash))
        top_a = sum(1 for _, cas, _, (na, ash, _) in top if is_single_instrument(cas, na, ash))
        print(f"    {t:<16}{len(ws):>6} | {flagged:>7}{100*flagged/len(ws):>5.0f}  {surv}/{len(top)}"
              f"     | {fl_a:>7}{100*fl_a/len(ws):>5.0f}  {top_a}/{len(top)}")

    # --- 3. the known batch weeks must be flagged by the right gate
    print("\n[3] known batch weeks (policy-tempo.md §3); 'must' = that gate has to flag it")
    ok = True
    for t, iw, want_site, must, want_title, must_a in KNOWN_BATCH_WEEKS:
        cas = pooled_cas.get((t, iw), 0)
        ns, sh, top = exact.get((t, iw), (0, 0.0, ""))
        na, ash, atop = exact_a.get((t, iw), (0, 0.0, 0))
        top2 = sum(n for _, n in pooled.get((t, iw), Counter()).most_common(2))
        d = is_diverse(cas, ns, sh)
        si = is_single_instrument(cas, na, ash)
        flagged = d is False
        if must:
            ok &= flagged and (want_site is None or top == want_site)
        if must_a:
            ok &= bool(si) and (want_title is None or want_title in (titles.get(atop) or ""))
        verdict = "FLAGGED" if flagged else ("NOT FLAGGED (!)" if must else "not flagged (expected)")
        verdict_a = "FLAGGED" if si else ("NOT FLAGGED (!)" if must_a else "not flagged (expected)")
        print(f"    {t}/{iw} events={cas}")
        print(f"      site gate  must={must}: n_sites={ns} top_site_share={sh:.2f} top_site={top} "
              f"top2_share={top2/cas if cas else 0:.2f} diverse={d} -> {verdict}")
        print(f"      instr gate must={must_a}: n_anchors={na} top_anchor_share={ash:.3f} "
              f"top_anchor={atop} ({ttl(atop)}) = {round(ash*cas)} events "
              f"single_instrument={si} -> {verdict_a}")
    # --- 4. per-level merge (what the service does) vs exact pooled, both gates
    disagree = disagree_a = 0
    checked = 0
    for (t, iw), cas in pooled_cas.items():
        if cas < DIVERSE_MIN_EVENTS:
            continue
        cells = []
        for lvl in {k[2] for k in agg if k[0] == t and k[1] == iw}:
            v = agg.get((t, iw, lvl))
            ns, sh, top = site_diversity(sites.get((t, iw, lvl)))
            na, ash, atop = anchor_diversity(anchors.get((t, iw, lvl)))
            cells.append({"cas": v[CAS], "n_sites": ns, "top_site_share": sh, "top_site": top,
                          "n_anchors": na, "top_anchor_share": ash, "top_anchor": atop})
        ns, sh, _ = exact[(t, iw)]
        na, ash, _ = exact_a[(t, iw)]
        checked += 1
        if row_diversity(cells)["diverse"] != is_diverse(cas, ns, sh):
            disagree += 1
        if row_instrument(cells)["single_instrument"] != is_single_instrument(cas, na, ash):
            disagree_a += 1
    print(f"\n[4] service per-level merge vs exact pooled gate: site {disagree}/{checked}, "
          f"instrument {disagree_a}/{checked} weeks disagree")
    print("\nRESULT:", "OK — every known batch week is flagged by its gate"
          if ok else "FAIL — a known batch week passed its gate")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=str, default=str(DEFAULT_DB))
    ap.add_argument("--stats", action="store_true",
                    help="Print the busiest recent weeks (topic='all') and exit")
    ap.add_argument("--dry-run", action="store_true",
                    help="Read-only (?mode=ro): compute in memory, print the site-diversity and "
                         "anchor-concentration gate reports, write nothing; exit 1 if a known "
                         "batch week is not flagged by its gate")
    args = ap.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    if args.dry_run:
        raise SystemExit(0 if dry_run(db_path) else 1)

    if args.stats:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        tw_cols = {r[1] for r in conn.execute("PRAGMA table_info(tracker_weekly)")}
        div_cols = (", n_sites, top_site_share, top_site" if "n_sites" in tw_cols
                    else ", 0, 0.0, ''")
        inst_cols = (", n_anchors, top_anchor_share, top_anchor" if "n_anchors" in tw_cols
                     else ", 0, 0.0, 0")
        print(f"  {'week':<9}{'level':<12}{'docs':>7}{'casc':>6}{'ment':>6}{'low':>6}{'prov':>6}"
              f"{'sites':>7}{'top%':>6}  {'top_site':<14}{'anchs':>6}{'top%':>6}  top_anchor")
        for r in conn.execute(
                "SELECT iso_week, admin_level, new_docs, cascade_events, cascade_events_mentions, "
                f"cascade_events_lowconf, cascade_events_prov{div_cols}{inst_cols} "
                "FROM tracker_weekly WHERE topic='all' ORDER BY iso_week DESC, admin_level LIMIT 30"):
            print(f"  {r[0]:<9}{r[1]:<12}{r[2]:>7}{r[3]:>6}{r[4]:>6}{r[5]:>6}{r[6]:>6}"
                  f"{r[7]:>7}{100*r[8]:>6.0f}  {r[9]:<14}{r[10]:>6}{100*r[11]:>6.0f}  {r[12]}")
        conn.close()
        return

    t0 = time.time()
    rows, n_docs, n_ev = build(db_path)
    print(f"tracker_weekly built: {rows:,} rows from {n_docs:,} docs + "
          f"{n_ev:,} diffusion events, {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
