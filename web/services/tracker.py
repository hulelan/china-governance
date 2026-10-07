"""Policy Tracker services — the live weekly feed + auto-matched cascades.

Step 3 of ``docs/research/daily-tracker-concept.md``. Everything here reads the
two tables the nightly pipeline precomputes (daily_sync.sh Phase 2c):

* ``tracker_weekly``   — (topic, iso_week, admin_level) → new_docs,
                         cascade_events, cascade_events_lowconf. Indexed on
                         (topic, iso_week); a page reads N weeks × ~7 levels.
* ``diffusion_events`` — one row per (source doc, anchor instrument) match with
                         match_type ∈ {citation, title_reissue, topic_genre},
                         anchor_level ∈ {central, provincial} (the province→city
                         hop, fidelity-provincial.md), source_implementing 0/1
                         (the source is a policy instrument vs. a readout /
                         explainer / news item that merely MENTIONS the anchor),
                         lag_days, the anchor's FIRST topic tag, and denormalized
                         titles/dates. ~33k rows, indexed on anchor_id/source_id/
                         anchor_level/source_implementing.

A "confirmed" cascade event everywhere on the page = citation|title_reissue AND
source_implementing=1. Mentions (confirmed match, source_implementing=0) are
shown only as a muted secondary "+N mentions" count — a locality's news page
citing an instrument is a reference, not an implementation (diffusion-fidelity.md
"implementing-instrument subset"). Requires the 2026-10 matcher build (the column
must exist; the nightly rebuilds it).

Plus ``documents``/``sites`` for issuer names and the anchor's full topic list —
always by primary key on a few dozen ids, never a cold aggregate scan. Each
page assembly is cached in-process for an hour (same pattern as /lens), which
is also the data's own refresh cadence (nightly).

Topic semantics (from build_tracker_rollup.py): ``diffusion_events.topic`` only
stores the anchor's first ``topics_algo`` tag, whereas the weekly rollup counts a
cascade under EVERY topic of its anchor. To keep the cascade list consistent
with the weekly table, this module resolves anchor → full tag list once (a
~3.7k-row PK join, cached) and filters on that, not on ``e.topic``.
"""
import re
import time
from collections import defaultdict
from datetime import date, timedelta
from statistics import median

CACHE_TTL = 3600  # seconds
_cache: dict = {}

ALL = "all"
CONFIRMED = ("citation", "title_reissue")
LOWCONF = "topic_genre"
DEFAULT_WEEKS = 8
MAX_WEEKS = 52
# Canonical column order for the weekly matrix (sub-national first after central).
LEVEL_ORDER = ["central", "provincial", "municipal", "district", "department",
               "media", "research"]
ACTIVE_LIMIT = 12       # anchors shown in "active cascades" — PER anchor_level
NEWEST_PER_ANCHOR = 4   # newest implementing docs listed per anchor
LEADERBOARD_LIMIT = 15

# Site-diversity gate on a week's confirmed cascade count (policy-tempo.md §3: the
# pooled bursts were single-portal archive batches — Guangzhou 51/83 in 2023-W01,
# Shenzhen 57/66 in 2020-W11, lvliang+npc on 生态环境法典 in 2026-W33 — so a raw
# burst can be one site's upload, not tempo). A week is `diverse` when it has at
# least DIVERSE_MIN_EVENTS cascade events (the memo's burst floor; below that the
# question is moot and the flag is None) spread over >= DIVERSE_MIN_SITES source
# sites with no single site supplying more than DIVERSE_MAX_SHARE of them.
# Thresholds from the live distribution (build_tracker_rollup.py --dry-run,
# 2026-10-07, topic='all', 449 weeks with >= 3 events): modal-site share is
# < 0.3 in 287 weeks, <= 0.5 in 408 (91%); above 0.5 are 41 weeks (9%), and the
# two known single-portal batches sit at 0.61 (Guangzhou 51/83) and 0.86
# (Shenzhen 57/66). 0.5 is a majority rule — "no one portal supplied more than
# half" — and keeps a 0.11 margin on the Guangzhou week that a 0.6 cut would pass
# by 0.014. n_sites >= 3 adds the two-portal 50/50 case (4 pooled weeks have
# exactly 2 sites). The third memo week (2026-W33, lvliang 15 + npc 14 of 75
# from 26 sites, share 0.20) is a one-ANCHOR concentration, not a site batch,
# and is deliberately NOT caught by this gate.
DIVERSE_MIN_EVENTS = 3
DIVERSE_MIN_SITES = 3
DIVERSE_MAX_SHARE = 0.5


def is_diverse(cascade_events, n_sites, top_site_share):
    """The gate. None when the week has too few events to judge (< DIVERSE_MIN_EVENTS),
    else True (multi-source week) / False (single-source batch)."""
    if not cascade_events or cascade_events < DIVERSE_MIN_EVENTS:
        return None
    return bool(n_sites >= DIVERSE_MIN_SITES and top_site_share <= DIVERSE_MAX_SHARE)


def row_diversity(cells):
    """Merge per-level cells ({cas, n_sites, top_site_share, top_site}) into one
    pooled week: n_sites summed over levels (exact unless a site's docs straddle
    levels — doc_identity gives per-DOCUMENT levels, so a few do; then this
    over-counts by at most the number of straddling sites) and the modal share
    from the per-level modal sites merged by key (the exact share can only be
    higher when the true modal site is not modal in every level, which makes
    this a slightly LENIENT approximation; --dry-run reports the disagreement
    rate against the exact pooled counter — 1 of 1,250 weeks on 2026-10-07).
    Returns {n_sites, top_site_share, top_site, diverse}."""
    cas = sum(c.get("cas", 0) for c in cells)
    n_sites = sum(c.get("n_sites", 0) for c in cells)
    per_site = defaultdict(int)
    for c in cells:
        if c.get("cas") and c.get("top_site"):
            per_site[c["top_site"]] += int(round(c["top_site_share"] * c["cas"]))
    top_site, top_n = (max(per_site.items(), key=lambda kv: (kv[1], kv[0]))
                       if per_site else ("", 0))
    share = round(top_n / cas, 4) if cas else 0.0
    return {"n_sites": n_sites, "top_site_share": share, "top_site": top_site,
            "diverse": is_diverse(cas, n_sites, share)}


_TAG_RE = re.compile(r"<[^>]+>")


def _clean(title) -> str:
    """Denormalized titles in diffusion_events can carry list-chrome HTML
    (<br/>, spans); strip tags and collapse whitespace for display."""
    return " ".join(_TAG_RE.sub(" ", title or "").split())


def _cached(key):
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < CACHE_TTL:
        return hit["data"]
    return None


def _store(key, data):
    _cache[key] = {"data": data, "ts": time.time()}
    return data


def iso_week_str(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def recent_weeks(n: int, today: date = None):
    """The last ``n`` ISO weeks ending with the current one, newest first:
    [(iso_week, monday_date_str), ...]. Computed from *today*, not from the
    table's max week — a handful of docs carry future publication dates and
    would otherwise drag the window into weeks that have not happened."""
    today = today or date.today()
    monday = today - timedelta(days=today.weekday())
    out = []
    for i in range(n):
        m = monday - timedelta(days=7 * i)
        out.append((iso_week_str(m), m.isoformat()))
    return out


def clamp_weeks(weeks) -> int:
    try:
        n = int(weeks)
    except (TypeError, ValueError):
        n = DEFAULT_WEEKS
    return max(1, min(MAX_WEEKS, n))


async def tables_present(db) -> bool:
    """True when both precomputed tables exist (the nightly has run step 1+2)."""
    hit = _cached("tables")
    if hit is not None:
        return hit
    n = await db.fetchval(
        """SELECT COUNT(*) FROM sqlite_master
           WHERE type='table' AND name IN ('diffusion_events', 'tracker_weekly')""")
    return _store("tables", n == 2)


async def get_topics(db):
    """Distinct tracker topics, 'all' first then alphabetical. Served by the
    (topic, iso_week) index — a DISTINCT over the index, no table read."""
    hit = _cached("topics")
    if hit is not None:
        return hit
    rows = await db.fetch("SELECT DISTINCT topic FROM tracker_weekly ORDER BY topic")
    topics = sorted((r["topic"] for r in rows if r["topic"] and r["topic"] != ALL),
                    key=str.lower)
    return _store("topics", [ALL] + topics)


async def _anchor_topics(db):
    """anchor_id → set of topics_algo tags for every anchor in diffusion_events.
    One PK join over ~3.7k anchors, cached for the hour."""
    hit = _cached("anchor_topics")
    if hit is not None:
        return hit
    rows = await db.fetch(
        """SELECT a.anchor_id, COALESCE(d.topics_algo, '') AS tags
           FROM (SELECT DISTINCT anchor_id FROM diffusion_events) a
           LEFT JOIN documents d ON d.id = a.anchor_id""")
    out = {}
    for r in rows:
        out[r["anchor_id"]] = {t for t in (r["tags"] or "").split(",") if t}
    return _store("anchor_topics", out)


def _anchor_in_topic(anchor_id, ev_topic, topic, amap) -> bool:
    if topic == ALL:
        return True
    tags = amap.get(anchor_id)
    if tags:
        return topic in tags
    return ev_topic == topic  # anchor not in documents (shouldn't happen) — fall back


async def _has_diversity_cols(db) -> bool:
    """True once the rollup has been rebuilt with the n_sites/top_site_share/top_site
    columns (2026-10-07). Before that, get_weekly reads the old column set and
    every week's `diverse` is None (no tag) — the app never fails on an old table."""
    hit = _cached("tw_diversity_cols")
    if hit is not None:
        return hit
    rows = await db.fetch("PRAGMA table_info(tracker_weekly)")
    cols = {r["name"] for r in rows}
    return _store("tw_diversity_cols", {"n_sites", "top_site_share", "top_site"} <= cols)


async def get_weekly(db, topic: str, weeks: int):
    """The last ``weeks`` ISO weeks × admin_level matrix for ``topic``.

    Returns {"weeks": [row...], "levels": [level...], "totals": {...}} where each
    row is {iso_week, week_start, is_current, cells: {level: {new, cas, low, prov, men,
    n_sites, top_site_share, top_site, diverse}}, new, cas, low, prov, men, n_sites,
    top_site_share, top_site, diverse}. Levels with no activity in the window are
    dropped so the table stays compact; order follows LEVEL_ORDER. ``cas`` is
    implementing-only; ``men`` is the confirmed-but-mention count. ``diverse`` is the
    site-diversity gate (is_diverse): None = too few events to judge, False = a
    single-source batch week (the template tags it; counts are NOT changed).
    """
    wk = recent_weeks(weeks)
    lo, hi = wk[-1][0], wk[0][0]
    div = await _has_diversity_cols(db)
    div_cols = ", n_sites, top_site_share, top_site" if div else ""
    rows = await db.fetch(
        f"""SELECT iso_week, admin_level, week_start, new_docs,
                  cascade_events, cascade_events_lowconf, cascade_events_prov,
                  cascade_events_mentions{div_cols}
           FROM tracker_weekly
           WHERE topic = $1 AND iso_week BETWEEN $2 AND $3""", topic, lo, hi)
    cells = defaultdict(dict)
    seen_levels = set()
    KEYS = ("new", "cas", "low", "prov", "men")
    DIV = {"n_sites": 0, "top_site_share": 0.0, "top_site": "", "diverse": None}
    for r in rows:
        if (r["new_docs"] or r["cascade_events"] or r["cascade_events_lowconf"]
                or r["cascade_events_prov"] or r["cascade_events_mentions"]):
            seen_levels.add(r["admin_level"])
        cell = {"new": r["new_docs"], "cas": r["cascade_events"],
                "low": r["cascade_events_lowconf"], "prov": r["cascade_events_prov"],
                "men": r["cascade_events_mentions"], **DIV}
        if div:
            cell.update(n_sites=r["n_sites"] or 0, top_site_share=r["top_site_share"] or 0.0,
                        top_site=r["top_site"] or "",
                        diverse=is_diverse(cell["cas"], r["n_sites"] or 0,
                                           r["top_site_share"] or 0.0))
        cells[r["iso_week"]][r["admin_level"]] = cell
    levels = [l for l in LEVEL_ORDER if l in seen_levels]
    levels += sorted(l for l in seen_levels if l not in LEVEL_ORDER)

    out_rows, totals = [], dict.fromkeys(KEYS, 0)
    level_totals = {l: dict.fromkeys(KEYS, 0) for l in levels}
    empty = {**dict.fromkeys(KEYS, 0), **DIV}
    for i, (iw, monday) in enumerate(wk):
        c = cells.get(iw, {})
        row = {"iso_week": iw, "week_start": monday, "is_current": i == 0,
               "cells": {l: c.get(l, dict(empty)) for l in levels}}
        row.update(dict.fromkeys(KEYS, 0))
        for l in levels:
            for k in KEYS:
                row[k] += row["cells"][l][k]
                level_totals[l][k] += row["cells"][l][k]
        for k in KEYS:
            totals[k] += row[k]
        row.update(row_diversity(list(row["cells"].values())) if div else DIV)
        out_rows.append(row)
    return {"weeks": out_rows, "levels": levels, "totals": totals,
            "level_totals": level_totals,
            "window_start": wk[-1][1], "window_end": wk[0][1]}


async def _issuers(db, ids):
    """id → {site_key, site_name, title_en} for a small id list (PK lookups)."""
    ids = sorted({i for i in ids if i})
    if not ids:
        return {}
    rows = await db.fetch(
        """SELECT d.id, d.site_key, s.name AS site_name, COALESCE(d.title_en, '') AS title_en
           FROM documents d LEFT JOIN sites s ON s.site_key = d.site_key
           WHERE d.id = ANY($1::int[])""", ids)
    return {r["id"]: dict(r) for r in rows}


async def get_active_cascades(db, topic: str, weeks: int):
    """Anchors with the newest confirmed implementing activity in the window.

    1. Scan the (small) events table for the date window — all topics, then
       filter by the anchor's full tag list in Python (see module docstring).
    2. Rank anchors by newest arrival, then by in-window distinct sources.
    3. For the top ACTIVE_LIMIT anchors, pull ALL their events (indexed by
       anchor_id) for the cascade-wide stats: distinct sources, median lag,
       first/newest arrival, low-confidence count, newest few docs.
    """
    wk = recent_weeks(weeks)
    today = date.today().isoformat()
    start = wk[-1][1]
    amap = await _anchor_topics(db)

    win = await db.fetch(
        """SELECT anchor_id, source_id, match_type, topic, source_date, anchor_level,
                  source_implementing
           FROM diffusion_events
           WHERE source_date BETWEEN $1 AND $2""", start, today)
    newest, in_win, low_win = {}, defaultdict(set), defaultdict(set)
    men_win = defaultdict(set)
    alevel = {}
    for r in win:
        if not _anchor_in_topic(r["anchor_id"], r["topic"], topic, amap):
            continue
        a = r["anchor_id"]
        alevel[a] = r["anchor_level"] or "central"
        if r["match_type"] == LOWCONF:
            low_win[a].add(r["source_id"])
            continue
        if not r["source_implementing"]:
            men_win[a].add(r["source_id"])  # confirmed match, but a mention — not a cascade
            continue
        in_win[a].add(r["source_id"])
        if r["source_date"] > newest.get(a, ""):
            newest[a] = r["source_date"]
    ranked = sorted(in_win, key=lambda a: (newest[a], len(in_win[a])), reverse=True)
    # Anchor-level aware: central instruments arrive far more often, so a single
    # newest-first cut filled all ACTIVE_LIMIT slots and provincial cascades never
    # surfaced here (only in the leaderboard / weekly cells). Take the top
    # ACTIVE_LIMIT per anchor_level, then keep the merged list in newest-arrival
    # order so the two levels interleave under their tags.
    per_level = defaultdict(list)
    for a in ranked:
        lvl = alevel.get(a, "central")
        if len(per_level[lvl]) < ACTIVE_LIMIT:
            per_level[lvl].append(a)
    chosen = {a for lst in per_level.values() for a in lst}
    top = [a for a in ranked if a in chosen]
    n_lowconf_only = len([a for a in low_win if a not in in_win])
    n_mentions_only = len([a for a in men_win if a not in in_win])
    if not top:
        return {"anchors": [], "n_active": 0, "n_lowconf_only": n_lowconf_only,
                "n_mentions_only": n_mentions_only,
                "window_start": start, "per_level_limit": ACTIVE_LIMIT}

    ev = await db.fetch(
        """SELECT anchor_id, source_id, match_type, lag_days, source_level,
                  anchor_date, anchor_title, source_date, source_title,
                  source_implementing
           FROM diffusion_events
           WHERE anchor_id = ANY($1::int[])
           ORDER BY source_date DESC""", top)
    by_anchor = defaultdict(list)
    for r in ev:
        by_anchor[r["anchor_id"]].append(r)

    newest_ids = []
    anchors = []
    for a in top:
        rows = by_anchor.get(a, [])
        conf = [r for r in rows if r["match_type"] in CONFIRMED and r["source_implementing"]]
        men = [r for r in rows if r["match_type"] in CONFIRMED and not r["source_implementing"]]
        low = [r for r in rows if r["match_type"] == LOWCONF]
        if not conf:
            continue
        lags = [r["lag_days"] for r in conf if r["lag_days"] is not None and r["lag_days"] >= 0]
        srcs = {r["source_id"] for r in conf}
        levels = defaultdict(int)
        for r in conf:
            levels[r["source_level"] or "unknown"] += 1
        newest_docs = []
        seen = set()
        for r in conf:  # already newest-first
            if r["source_id"] in seen:
                continue
            seen.add(r["source_id"])
            newest_docs.append({
                "id": r["source_id"], "title": _clean(r["source_title"]),
                "level": r["source_level"] or "unknown", "lag": r["lag_days"],
                "date": r["source_date"], "match": r["match_type"],
                "in_window": r["source_id"] in in_win[a],
            })
            if len(newest_docs) >= NEWEST_PER_ANCHOR:
                break
        newest_ids += [d["id"] for d in newest_docs]
        anchors.append({
            "id": a, "title": _clean(conf[0]["anchor_title"]),
            "anchor_level": alevel.get(a, "central"),
            "date": conf[0]["anchor_date"] or "",
            "topics": sorted(amap.get(a) or []),
            "n_sources": len(srcs), "n_in_window": len(in_win[a]),
            "n_mentions": len({r["source_id"] for r in men}),
            "n_lowconf": len({r["source_id"] for r in low}),
            "median_lag": int(median(lags)) if lags else None,
            "first_date": min(r["source_date"] for r in conf),
            "newest_date": newest[a],
            "levels": sorted(levels.items(), key=lambda kv: -kv[1]),
            "newest": newest_docs,
        })

    iss = await _issuers(db, newest_ids + [x["id"] for x in anchors])
    for x in anchors:
        meta = iss.get(x["id"], {})
        x["title_en"] = meta.get("title_en", "")
        x["issuer"] = meta.get("site_name") or ""
        for d in x["newest"]:
            m = iss.get(d["id"], {})
            d["issuer"] = m.get("site_name") or m.get("site_key") or ""
    return {"anchors": anchors, "n_active": len(ranked),
            "n_lowconf_only": n_lowconf_only, "n_mentions_only": n_mentions_only,
            "window_start": start, "per_level_limit": ACTIVE_LIMIT}


async def get_leaderboard(db, anchor_level: str = "central"):
    """Most-cascaded instruments across ALL topics: anchors of ``anchor_level``
    ('central' | 'provincial') ranked by distinct implementing sources (sites)
    over confirmed IMPLEMENTING signals (source_implementing=1); the confirmed
    mentions are carried as a secondary ``mentions`` count. One grouped PK join
    of the confirmed events with documents (for site_key); cached an hour per level."""
    key = ("leaderboard", anchor_level)
    hit = _cached(key)
    if hit is not None:
        return hit
    amap = await _anchor_topics(db)
    rows = await db.fetch(
        """SELECT e.anchor_id, MIN(e.anchor_title) AS title, MIN(e.anchor_date) AS adate,
                  COUNT(DISTINCT CASE WHEN e.source_implementing THEN d.site_key END) AS localities,
                  COUNT(DISTINCT CASE WHEN e.source_implementing THEN e.source_id END) AS docs,
                  COUNT(DISTINCT CASE WHEN NOT e.source_implementing THEN e.source_id END) AS mentions,
                  MAX(CASE WHEN e.source_implementing THEN e.source_date END) AS newest
           FROM diffusion_events e JOIN documents d ON d.id = e.source_id
           WHERE e.match_type IN ('citation', 'title_reissue')
             AND e.anchor_level = $2
           GROUP BY e.anchor_id
           HAVING localities > 0
           ORDER BY localities DESC, docs DESC
           LIMIT $1""", LEADERBOARD_LIMIT, anchor_level)
    ids = [r["anchor_id"] for r in rows]
    lag_rows = await db.fetch(
        """SELECT anchor_id, lag_days FROM diffusion_events
           WHERE anchor_id = ANY($1::int[])
             AND match_type IN ('citation', 'title_reissue')
             AND source_implementing = 1
             AND lag_days IS NOT NULL AND lag_days >= 0""", ids) if ids else []
    lags = defaultdict(list)
    for r in lag_rows:
        lags[r["anchor_id"]].append(r["lag_days"])
    board = []
    for r in rows:
        a = r["anchor_id"]
        board.append({
            "id": a, "title": _clean(r["title"]), "date": r["adate"] or "",
            "localities": r["localities"], "docs": r["docs"], "newest": r["newest"],
            "mentions": r["mentions"],
            "median_lag": int(median(lags[a])) if lags[a] else None,
            "topics": sorted(amap.get(a) or []),
        })
    ids_board = [b["id"] for b in board]
    if anchor_level == "provincial" and ids_board:
        # Label each provincial instrument by its issuing site (the province).
        iss = await _issuers(db, ids_board)
        for b in board:
            b["issuer"] = (iss.get(b["id"]) or {}).get("site_name") or ""
    return _store(key, board)


async def get_tracker(db, topic: str = ALL, weeks=DEFAULT_WEEKS):
    """Assemble the whole /tracker page for (topic, weeks); cached an hour.
    Returns None when the precomputed tables are absent (nightly not yet run)."""
    if not await tables_present(db):
        return None
    topics = await get_topics(db)
    topic = topic if topic in topics else ALL
    n = clamp_weeks(weeks)
    key = ("page", topic, n)
    hit = _cached(key)
    if hit is not None:
        return hit
    data = {
        "topic": topic, "weeks": n, "topics": topics,
        "weekly": await get_weekly(db, topic, n),
        "cascades": await get_active_cascades(db, topic, n),
        "leaderboard": await get_leaderboard(db, "central"),
        "leaderboard_prov": await get_leaderboard(db, "provincial"),
        "today": date.today().isoformat(),
        "this_week": iso_week_str(date.today()),
    }
    return _store(key, data)
