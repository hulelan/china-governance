#!/usr/bin/env python3
"""Nightly regression test for the corpus's known-good analytical facts.

Rationale: docs/research/corpus-lessons.md B5. The consistency review found build
drift, and a resolver fix once introduced a regression that only a manual review
caught. The known cascades should be asserted automatically after every rebuild
and fail loudly — one-off audit becomes structure.

Runs READ-ONLY (`?mode=ro`) against documents.db, after the Phase 2c rebuilds of
diffusion_events / tracker_weekly / site_stats and BEFORE Phase 3 publishes
(daily_sync.sh Phase 2d). Every check prints `PASS`/`FAIL` with the measured value;
exit status is non-zero if ANY check fails. All queries hit indexes (<1s total).

    python3 scripts/validate_cascades.py                 # default thresholds
    python3 scripts/validate_cascades.py --db other.db
    python3 scripts/validate_cascades.py --set CXGH_EDGES_MAX=2000     # override a
        # threshold constant (any name below) — used to prove the test bites.

The publish is NOT aborted on failure (fresh data with a regression still beats
stale data); daily_sync just logs the failing lines and flags the Telegram report.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "documents.db"

# =============================================================================
# THRESHOLDS — every tolerance lives here. Each comment says what regression the
# check catches. Override any one at the CLI with `--set NAME=VALUE`.
# =============================================================================

# --- 1. Boost-consumption cascade (提振消费专项行动方案, 2025-03) -----------------
# The worked proof in docs/research/consumption-diffusion.md: the central 方案 is
# re-issued as a provincial 实施方案 by Guangdong, Jiangsu and Beijing at known lags.
# Catches: a title_reissue stem/cue regression (the rows vanish), a
# source_implementing gate regression (the rows flip to 0), a date-parsing
# regression (the lags drift), or the anchor pool losing the central doc.
BOOST_ANCHOR_ID = 12650974                    # 中共中央办公厅 国务院办公厅印发《提振消费专项行动方案》
BOOST_ANCHOR_TITLE_KEY = "提振消费专项行动方案"  # pool = central anchors whose title carries this
BOOST_EXPECTED_LAGS = {                        # province → (lag_days, site_key prefix, title key)
    "Guangdong": (52, "gd", "广东省"),
    "Jiangsu": (82, "js", "江苏省"),
    "Beijing": (116, "bj", "北京市"),
}
BOOST_LAG_TOLERANCE = 2                        # ± days

# --- 2. 城乡规划法 citations: TWO metrics, two bands --------------------------
# The single most-cited framework law, and the canary for the whole resolver: a
# matcher that over-resolves (the 河南省实施办法 proxy-target bug) pushes it DOWN as
# edges get stolen; a normalisation regression or a broken `citations` rebuild pushes
# it down too; a containment-gate regression (news titles counted as citations)
# pushes it UP.
#
# These used to be ONE check named `cxgh_inbound` that printed "inbound citations"
# while measuring COUNT(*) = EDGE ROWS. `doc_inbound` meanwhile calls its
# COUNT(DISTINCT source_id) column `inbound`, so the same word named both metrics and
# a healthy +16 edges read as a 235-citer drop when the two were compared across
# nights (docs/working/qa-cxgh-citer-drop.md §0). Both are now asserted separately:
#   edges  = raw resolved rows, what citation_rank weights (today 2,158)
#   citers = COUNT(DISTINCT source_id), self-cites dropped, what doc_inbound.inbound
#            stores (today 1,907)
# The gap between the bands is the DUPLICATE-EDGE OVERHANG (251 today: one document
# citing the law under 2+ distinct target_ref strings / tiers, which
# UNIQUE(source_id, target_ref, citation_type) permits). Asserting both makes that
# overhang a monitored quantity instead of a blind spot.
# CHANGED 2026-10-07 from 12747143 (npc, 2015 edition) to 12685270 (mee, 2019): the
# law is held 3× under a byte-identical title (mee 12685270 / npc 12742122 / npc
# 12747143, all central, all genre 'law'), and until the resolver fix in this same
# commit the copy that collected every edge was whichever row an UNORDERED SELECT
# scanned LAST — the highest id, by accident of rowid order. TitleMatcher's documented
# (genre_rank, level_rank, LOWEST id) tie-break now actually decides, so the 2,158
# edges move to the lowest-id copy. Verified read-only against the live corpus before
# the rebuild. If this id ever reads ~0 again, check the tie-break, not the graph.
CXGH_ID = 12685270                             # 中华人民共和国城乡规划法 (mee, lowest-id copy)
CXGH_EDGES_MIN = 1900                          # band ±~12% around 2,141 edges (unchanged)
CXGH_EDGES_MAX = 2400
CXGH_CITERS_MIN = 1680                         # band ±~12% around 1,907 distinct citers
CXGH_CITERS_MAX = 2140

# --- 3. AI+ anchor: implementing vs mention-only ------------------------------
# 国务院关于深入实施“人工智能+”行动的意见 draws many 党组会议 readouts / 解读 / media
# reposts. The source_implementing gate (1a08989) separates them. Catches: the gate
# being bypassed (mention-only collapses toward 0 and implementing balloons), or
# the cue match breaking (implementing collapses).
# The anchor is identified by its doc_identity INSTRUMENT pool (the matcher's
# anchor_id is the pool's canonical copy, which need not be this gov.cn id — the
# same text sits on gov.cn twice plus mee/cac/zj mirrors).
AIPLUS_ID = 900039770
AIPLUS_IMPL_MIN = 20
AIPLUS_IMPL_MAX = 60
# topic_genre is the weakest tier and grows as AI documents arrive inside the anchor's
# 365-day window, so it gets a loose ceiling that catches a runaway, not a tight band.
AIPLUS_TOPIC_MAX = 400
# and: mention-only (source_implementing=0) must EXCEED implementing — i.e. the
# gate is actually active, not defaulted to 1 for every row.

# --- 4. Proxy-target guard -----------------------------------------------------
# Two documented false targets. 河南省实施《城乡规划法》办法 is a wrapper whose title
# CONTAINS the law's title; a core-extraction regression resolves 《城乡规划法》 refs
# to it instead of the law (was ~2,100 edges before 7f889e9). 北京发布《深化改革提振
# 消费专项行动方案》 is a NEWS page sharing the Beijing 方案's named instrument; it
# must never collect citations or act as a diffusion anchor (e1ff3b7).
HENAN_WRAPPER_ID = 12749787
HENAN_WRAPPER_INBOUND_MAX = 20
BJ_NEWS_ID = 900105357
BJ_NEWS_INBOUND_MAX = 5
# and: BJ_NEWS_ID must have ZERO rows as diffusion_events.anchor_id.

# --- 5. Table presence / size sanity -------------------------------------------
# Catches: a builder that ran but wrote nothing (DELETE+INSERT with an empty
# INSERT), a half-finished rebuild (timeout mid-pass), or a stats table that is
# stale relative to documents. Bands are wide (the corpus grows nightly).
DIFFUSION_ROWS_MIN = 20_000
DIFFUSION_ROWS_MAX = 80_000
TRACKER_WEEKLY_ROWS_MIN = 30_000
NONEMPTY_TABLES = ("site_stats", "corpus_stats", "doc_issuers")
CORPUS_STATS_TOTAL_TOLERANCE = 0.02           # corpus_stats.total within 2% of COUNT(*)

# --- 6. Top-of-rank sanity -----------------------------------------------------
# The top of citation_rank must be formal framework instruments (法/条例/规定/办法/
# 意见), not news or meeting readouts. Catches: a containment-gate regression that
# lets 新闻/解读/会议 titles absorb citations (e1ff3b7), or a weighting bug in
# compute_scores. NOTE this is a GENRE check on the title, not a host-site check —
# the live #1 (政府信息公开条例) is a central law reposted on a municipal site.
TOP_RANK_N = 5
TOP_RANK_INSTRUMENT_RE = re.compile(r"(法|条例|规定|办法|意见)")
TOP_RANK_NEWS_RE = re.compile(
    r"(发布|解读|一图|图解|召开|会议|讲话|新闻|报道|动态|快讯|问答|访谈|学习|贯彻落实.*精神)"
)
TOP_RANK_OK_GENRES = {"law", "regulation", "policy_issuance", "action_plan", "opinion", "decision", "decree"}

# =============================================================================


class Result:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failed: list[str] = []

    def record(self, name: str, ok: bool, measured: str) -> None:
        tag = "PASS" if ok else "FAIL"
        self.lines.append(f"{tag}  {name}: {measured}")
        if not ok:
            self.failed.append(name)


def _one(conn: sqlite3.Connection, sql: str, *params) -> object:
    row = conn.execute(sql, params).fetchone()
    return row[0] if row else None


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return _one(conn, "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", name) is not None


# --- 1 -----------------------------------------------------------------------
def check_boost_cascade(conn: sqlite3.Connection, r: Result) -> None:
    pool = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT anchor_id FROM diffusion_events "
            "WHERE anchor_level='central' AND anchor_title LIKE ?",
            (f"%{BOOST_ANCHOR_TITLE_KEY}%",),
        )
    ]
    if BOOST_ANCHOR_ID not in pool:
        pool.append(BOOST_ANCHOR_ID)
    marks = ",".join("?" * len(pool))
    rows = conn.execute(
        f"SELECT source_id, lag_days, source_title, d.site_key "
        f"FROM diffusion_events e JOIN documents d ON d.id = e.source_id "
        f"WHERE e.anchor_id IN ({marks}) AND e.match_type='title_reissue' "
        f"AND e.source_implementing=1 AND e.source_level='provincial'",
        pool,
    ).fetchall()
    for prov, (lag, site_prefix, title_key) in BOOST_EXPECTED_LAGS.items():
        hits = [
            (sid, l)
            for sid, l, title, site in rows
            if l is not None
            and abs(l - lag) <= BOOST_LAG_TOLERANCE
            and (site.startswith(site_prefix) or title_key in (title or ""))
        ]
        measured = (
            f"lag {hits[0][1]}d (doc {hits[0][0]}; expected {lag}±{BOOST_LAG_TOLERANCE}, "
            f"anchor pool {pool})"
            if hits
            else f"NO title_reissue/implementing row at {lag}±{BOOST_LAG_TOLERANCE}d "
            f"(anchor pool {pool}; provincial lags seen: "
            f"{sorted(l for _, l, _, _ in rows if l is not None)[:12]})"
        )
        r.record(f"boost_cascade_{prov}", bool(hits), measured)


# --- 2 -----------------------------------------------------------------------
def check_cxgh_citations(conn: sqlite3.Connection, r: Result) -> None:
    """Two named checks, two bands: edge rows and distinct citers. Never collapse
    them back into one — the words are not interchangeable (see §2 above)."""
    # edges  = every resolved row, exactly what citation_rank weights
    # citers = distinct sources with self-cites dropped, exactly doc_inbound.inbound
    edges, citers = conn.execute(
        "SELECT COUNT(*), "
        "       COUNT(DISTINCT CASE WHEN source_id <> target_id THEN source_id END) "
        "FROM citations WHERE target_id=?",
        (CXGH_ID,),
    ).fetchone()
    dupes = edges - citers  # duplicate-edge overhang (same citer, 2+ ref strings/tiers)
    r.record(
        "cxgh_edges",
        CXGH_EDGES_MIN <= edges <= CXGH_EDGES_MAX,
        f"{edges} citation EDGE rows on doc {CXGH_ID} "
        f"(band [{CXGH_EDGES_MIN}, {CXGH_EDGES_MAX}]; {dupes} duplicate-edge overhang)",
    )
    r.record(
        "cxgh_citers",
        CXGH_CITERS_MIN <= citers <= CXGH_CITERS_MAX,
        f"{citers} DISTINCT citing documents, self-cites dropped "
        f"(band [{CXGH_CITERS_MIN}, {CXGH_CITERS_MAX}]; {edges} edges)",
    )


# --- 3 -----------------------------------------------------------------------
def check_aiplus_gate(conn: sqlite3.Connection, r: Result) -> None:
    """AI+ cascade size, counted on the CONFIRMED match tiers only.

    Why the split (2026-10-07): this check used to count every `source_implementing=1`
    event regardless of match_type, and it FAILED at 131 against a band of [20, 60] after
    a rebuild in which the cascade itself had not changed. 102 of those 131 were
    `topic_genre`, the matcher's own weakest tier ("probable-but-unconfirmed
    implementation" — same topic tag, implementing genre, inside a 365-day window). That
    tier is gated on the anchor's `citation_rank >= TOPIC_ANCHOR_CR`, and the
    mirror-determinism fix consolidated the AI+ edges onto the pool's canonical copy,
    which pushed the anchor over the gate and switched the tier on. The AI+ opinion is
    also recent (2025-08), so its topic window is wide open and fills as AI documents
    arrive.

    The memos (`ai-plus-fidelity.md`, `ai-governance-diffusion.md`) quote the CONFIRMED
    count, and on the same rebuild that is citation 21 + title_reissue 8 = 29, inside the
    original band. So the band was never wrong about the cascade; the metric was
    ambiguous, exactly like `cxgh_inbound` counting edges while saying citers. Confirmed
    and topic_genre are now separate checks with their own bands, so a composition shift
    is visible instead of being read as a cascade change.
    """
    pool_sql = ("anchor_id IN (SELECT doc_id FROM doc_identity WHERE instrument_id = "
                "(SELECT instrument_id FROM doc_identity WHERE doc_id=?))")
    confirmed = _one(
        conn,
        f"SELECT COUNT(*) FROM diffusion_events WHERE {pool_sql} AND source_implementing=1 "
        "AND match_type IN ('citation', 'title_reissue')",
        AIPLUS_ID,
    )
    topical = _one(
        conn,
        f"SELECT COUNT(*) FROM diffusion_events WHERE {pool_sql} AND source_implementing=1 "
        "AND match_type = 'topic_genre'",
        AIPLUS_ID,
    )
    mention = _one(
        conn,
        f"SELECT COUNT(*) FROM diffusion_events WHERE {pool_sql} AND source_implementing=0",
        AIPLUS_ID,
    )
    r.record(
        "aiplus_implementing",
        AIPLUS_IMPL_MIN <= confirmed <= AIPLUS_IMPL_MAX,
        f"{confirmed} CONFIRMED implementing events, citation+title_reissue "
        f"(band [{AIPLUS_IMPL_MIN}, {AIPLUS_IMPL_MAX}]; {topical} topic_genre excluded)",
    )
    r.record(
        "aiplus_topic_genre",
        topical <= AIPLUS_TOPIC_MAX,
        f"{topical} topic_genre (probable-but-unconfirmed) events (max {AIPLUS_TOPIC_MAX})",
    )
    r.record(
        "aiplus_source_gate",
        mention > confirmed,
        f"{mention} mention-only vs {confirmed} confirmed implementing "
        "(gate active iff mention > confirmed)",
    )


# --- 4 -----------------------------------------------------------------------
def check_proxy_targets(conn: sqlite3.Connection, r: Result) -> None:
    henan = _one(conn, "SELECT COUNT(*) FROM citations WHERE target_id=?", HENAN_WRAPPER_ID)
    r.record(
        "proxy_henan_wrapper",
        henan <= HENAN_WRAPPER_INBOUND_MAX,
        f"{henan} inbound on 河南省实施《城乡规划法》办法 (max {HENAN_WRAPPER_INBOUND_MAX})",
    )
    bj_in = _one(conn, "SELECT COUNT(*) FROM citations WHERE target_id=?", BJ_NEWS_ID)
    bj_anchor = _one(conn, "SELECT COUNT(*) FROM diffusion_events WHERE anchor_id=?", BJ_NEWS_ID)
    r.record(
        "proxy_bj_news_page",
        bj_in <= BJ_NEWS_INBOUND_MAX and bj_anchor == 0,
        f"{bj_in} inbound (max {BJ_NEWS_INBOUND_MAX}), {bj_anchor} rows as diffusion anchor (must be 0)",
    )


# --- 5 -----------------------------------------------------------------------
def check_tables(conn: sqlite3.Connection, r: Result) -> None:
    de = _one(conn, "SELECT COUNT(*) FROM diffusion_events")
    r.record(
        "diffusion_events_size",
        DIFFUSION_ROWS_MIN <= de <= DIFFUSION_ROWS_MAX,
        f"{de} rows (band [{DIFFUSION_ROWS_MIN}, {DIFFUSION_ROWS_MAX}])",
    )
    tw = _one(conn, "SELECT COUNT(*) FROM tracker_weekly")
    r.record("tracker_weekly_size", tw > TRACKER_WEEKLY_ROWS_MIN, f"{tw} rows (min {TRACKER_WEEKLY_ROWS_MIN})")
    counts = {}
    for t in NONEMPTY_TABLES:
        counts[t] = _one(conn, f"SELECT COUNT(*) FROM {t}") if _table_exists(conn, t) else None
    r.record(
        "stats_tables_nonempty",
        all(c for c in counts.values()),
        ", ".join(f"{t}={c if c is not None else 'MISSING'}" for t, c in counts.items()),
    )
    total_docs = _one(conn, "SELECT COUNT(*) FROM documents")
    cs_total = _one(conn, "SELECT value FROM corpus_stats WHERE key='total'") or 0
    drift = abs(cs_total - total_docs) / max(total_docs, 1)
    r.record(
        "corpus_stats_total",
        drift <= CORPUS_STATS_TOTAL_TOLERANCE,
        f"corpus_stats.total={cs_total} vs COUNT(*)={total_docs} (drift {drift:.2%}, max {CORPUS_STATS_TOTAL_TOLERANCE:.0%})",
    )


# --- 6 -----------------------------------------------------------------------
def check_top_rank(conn: sqlite3.Connection, r: Result) -> None:
    rows = conn.execute(
        "SELECT id, title, algo_doc_type, citation_rank FROM documents "
        "WHERE citation_rank IS NOT NULL ORDER BY citation_rank DESC LIMIT ?",
        (TOP_RANK_N,),
    ).fetchall()
    bad = []
    for doc_id, title, genre, rank in rows:
        title = title or ""
        if (
            not TOP_RANK_INSTRUMENT_RE.search(title)
            or TOP_RANK_NEWS_RE.search(title)
            or (genre and genre not in TOP_RANK_OK_GENRES)
        ):
            bad.append(f"{doc_id} [{genre}] {title[:40]}")
    summary = "; ".join(f"{doc_id}:{(title or '')[:18]}({rank:.0f})" for doc_id, title, _, rank in rows)
    r.record(
        "top_rank_instruments",
        len(rows) == TOP_RANK_N and not bad,
        f"top-{TOP_RANK_N}: {summary}" + (f" | NON-INSTRUMENT: {bad}" if bad else ""),
    )


CHECKS = (
    check_boost_cascade,
    check_cxgh_citations,
    check_aiplus_gate,
    check_proxy_targets,
    check_tables,
    check_top_rank,
)


def apply_overrides(overrides: list[str]) -> None:
    g = globals()
    for item in overrides:
        name, _, raw = item.partition("=")
        if name not in g or not name.isupper():
            sys.exit(f"--set: unknown threshold {name!r}")
        cur = g[name]
        g[name] = type(cur)(raw) if isinstance(cur, (int, float)) and not isinstance(cur, bool) else raw
        print(f"override  {name} = {g[name]!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--set", action="append", default=[], metavar="NAME=VALUE",
                    help="override a threshold constant (repeatable)")
    args = ap.parse_args()
    apply_overrides(args.set)

    t0 = time.time()
    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True, timeout=30)
    res = Result()
    for check in CHECKS:
        try:
            check(conn, res)
        except Exception as exc:  # a missing table/column is itself a regression
            res.record(check.__name__, False, f"EXCEPTION {type(exc).__name__}: {exc}")
    conn.close()

    for line in res.lines:
        print(line)
    n = len(res.lines)
    if res.failed:
        print(f"VALIDATION FAIL: {len(res.failed)}/{n} checks failed: {', '.join(res.failed)} "
              f"({time.time() - t0:.1f}s)")
        return 1
    print(f"VALIDATION PASS: {n}/{n} checks ({time.time() - t0:.1f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
