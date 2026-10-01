"""Policy Tracker services — the live weekly feed + auto-matched cascades.

Step 3 of ``docs/research/daily-tracker-concept.md``. Everything here reads the
two tables the nightly pipeline precomputes (daily_sync.sh Phase 2c):

* ``tracker_weekly``   — (topic, iso_week, admin_level) → new_docs,
                         cascade_events, cascade_events_lowconf. Indexed on
                         (topic, iso_week); a page reads N weeks × ~7 levels.
* ``diffusion_events`` — one row per (source doc, anchor instrument) match with
                         match_type ∈ {citation, title_reissue, topic_genre},
                         anchor_level ∈ {central, provincial} (the province→city
                         hop, fidelity-provincial.md), lag_days, the anchor's
                         FIRST topic tag, and denormalized titles/dates. ~33k
                         rows, indexed on anchor_id/source_id/anchor_level.

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
ACTIVE_LIMIT = 12       # anchors shown in "active cascades"
NEWEST_PER_ANCHOR = 4   # newest implementing docs listed per anchor
LEADERBOARD_LIMIT = 15


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


async def get_weekly(db, topic: str, weeks: int):
    """The last ``weeks`` ISO weeks × admin_level matrix for ``topic``.

    Returns {"weeks": [row...], "levels": [level...], "totals": {...}} where each
    row is {iso_week, week_start, is_current, cells: {level: {new, cas, low}},
    new, cas, low}. Levels with no activity in the window are dropped so the
    table stays compact; order follows LEVEL_ORDER.
    """
    wk = recent_weeks(weeks)
    lo, hi = wk[-1][0], wk[0][0]
    rows = await db.fetch(
        """SELECT iso_week, admin_level, week_start, new_docs,
                  cascade_events, cascade_events_lowconf, cascade_events_prov
           FROM tracker_weekly
           WHERE topic = $1 AND iso_week BETWEEN $2 AND $3""", topic, lo, hi)
    cells = defaultdict(dict)
    seen_levels = set()
    KEYS = ("new", "cas", "low", "prov")
    for r in rows:
        if (r["new_docs"] or r["cascade_events"] or r["cascade_events_lowconf"]
                or r["cascade_events_prov"]):
            seen_levels.add(r["admin_level"])
        cells[r["iso_week"]][r["admin_level"]] = {
            "new": r["new_docs"], "cas": r["cascade_events"],
            "low": r["cascade_events_lowconf"], "prov": r["cascade_events_prov"]}
    levels = [l for l in LEVEL_ORDER if l in seen_levels]
    levels += sorted(l for l in seen_levels if l not in LEVEL_ORDER)

    out_rows, totals = [], dict.fromkeys(KEYS, 0)
    level_totals = {l: dict.fromkeys(KEYS, 0) for l in levels}
    for i, (iw, monday) in enumerate(wk):
        c = cells.get(iw, {})
        row = {"iso_week": iw, "week_start": monday, "is_current": i == 0,
               "cells": {l: c.get(l, dict.fromkeys(KEYS, 0)) for l in levels}}
        row.update(dict.fromkeys(KEYS, 0))
        for l in levels:
            for k in KEYS:
                row[k] += row["cells"][l][k]
                level_totals[l][k] += row["cells"][l][k]
        for k in KEYS:
            totals[k] += row[k]
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
        """SELECT anchor_id, source_id, match_type, topic, source_date, anchor_level
           FROM diffusion_events
           WHERE source_date BETWEEN $1 AND $2""", start, today)
    newest, in_win, low_win = {}, defaultdict(set), defaultdict(set)
    alevel = {}
    for r in win:
        if not _anchor_in_topic(r["anchor_id"], r["topic"], topic, amap):
            continue
        a = r["anchor_id"]
        alevel[a] = r["anchor_level"] or "central"
        if r["match_type"] == LOWCONF:
            low_win[a].add(r["source_id"])
            continue
        in_win[a].add(r["source_id"])
        if r["source_date"] > newest.get(a, ""):
            newest[a] = r["source_date"]
    ranked = sorted(in_win, key=lambda a: (newest[a], len(in_win[a])), reverse=True)
    top = ranked[:ACTIVE_LIMIT]
    n_lowconf_only = len([a for a in low_win if a not in in_win])
    if not top:
        return {"anchors": [], "n_active": 0, "n_lowconf_only": n_lowconf_only,
                "window_start": start}

    ev = await db.fetch(
        """SELECT anchor_id, source_id, match_type, lag_days, source_level,
                  anchor_date, anchor_title, source_date, source_title
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
        conf = [r for r in rows if r["match_type"] in CONFIRMED]
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
            "n_lowconf_only": n_lowconf_only, "window_start": start}


async def get_leaderboard(db, anchor_level: str = "central"):
    """Most-cascaded instruments across ALL topics: anchors of ``anchor_level``
    ('central' | 'provincial') ranked by distinct implementing sources (sites)
    over confirmed signals. One grouped PK join of the confirmed events with
    documents (for site_key); cached an hour per level."""
    key = ("leaderboard", anchor_level)
    hit = _cached(key)
    if hit is not None:
        return hit
    amap = await _anchor_topics(db)
    rows = await db.fetch(
        """SELECT e.anchor_id, MIN(e.anchor_title) AS title, MIN(e.anchor_date) AS adate,
                  COUNT(DISTINCT d.site_key) AS localities,
                  COUNT(DISTINCT e.source_id) AS docs,
                  MAX(e.source_date) AS newest
           FROM diffusion_events e JOIN documents d ON d.id = e.source_id
           WHERE e.match_type IN ('citation', 'title_reissue')
             AND e.anchor_level = $2
           GROUP BY e.anchor_id
           ORDER BY localities DESC, docs DESC
           LIMIT $1""", LEADERBOARD_LIMIT, anchor_level)
    ids = [r["anchor_id"] for r in rows]
    lag_rows = await db.fetch(
        """SELECT anchor_id, lag_days FROM diffusion_events
           WHERE anchor_id = ANY($1::int[])
             AND match_type IN ('citation', 'title_reissue')
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
