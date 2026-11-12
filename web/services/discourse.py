"""Global-discourse tracker (/discourse): concept x speaker type x ISO week.

Reads only the two tables scripts/build_discourse_weekly.py precomputes nightly
(daily_sync.sh Phase 2c), the way /tracker reads tracker_weekly:

* ``discourse_weekly(concept, speaker, iso_week, docs, denom)`` -- docs of a speaker
  type that week using the concept (one copy per title per speaker per week), and
  the speaker's deduped total that week. concept='_all' rows carry the denominator
  for weeks where a concept never appears.
* ``discourse_concepts(concept, label_en, family, pattern)`` -- the vocabulary.

Every query is either a PK-prefix read on one concept (+ '_all') or an iso_week
range read on the week index; nothing touches ``documents``. Page assemblies are
cached in-process for an hour (the data changes nightly).
"""
import time
from collections import defaultdict

from web.services.discourse_vocab import FAMILIES, SPEAKERS, SPEAKER_LABELS
from web.services.tracker import clamp_weeks, recent_weeks

CACHE_TTL = 3600
_cache: dict = {}

ALL = "_all"
DEFAULT_CONCEPT = "全球南方"
DEFAULT_WEEKS = 12
THIN = 30            # a speaker-week with fewer deduped docs is flagged thin
TRAIL = 8            # trailing weeks for the "new this week" baseline
JUMP_MIN = 3         # this-week docs needed to call a jump
JUMP_RATIO = 2.0     # ... and at least this multiple of the trailing mean
NEW_LIMIT = 30
# Media speakers whose crawl is dense only from 2025 (global-discourse-map.md, Design).
MEDIA_SPEAKERS = ("state_media", "commentary", "business_press")
FAMILY_LABELS = {
    "doctrine": "Doctrine", "initiatives": "Global initiatives", "world_order": "World order",
    "civilization": "Civilization", "knowledge": "Knowledge & discourse power",
    "foil": "Foils & rival terms", "counter_term": "Counter-terms",
}


def _cached(key):
    hit = _cache.get(key)
    if hit and time.time() - hit["ts"] < CACHE_TTL:
        return hit["data"]
    return None


def _store(key, data):
    _cache[key] = {"data": data, "ts": time.time()}
    return data


def rate(docs, denom):
    """Per 1,000 documents of that speaker type; None when there is no denominator."""
    return round(1000.0 * docs / denom, 1) if denom else None


async def tables_present(db) -> bool:
    n = await db.fetchval(
        """SELECT COUNT(*) FROM sqlite_master
           WHERE type='table' AND name IN ('discourse_weekly', 'discourse_concepts')""")
    return n == 2


async def get_concepts(db, since_week):
    """Vocabulary grouped by family, each with its window total (all speakers)."""
    rows = await db.fetch("SELECT concept, label_en, family, pattern FROM discourse_concepts")
    tot = {r["concept"]: r["n"] for r in await db.fetch(
        """SELECT concept, SUM(docs) AS n FROM discourse_weekly
           WHERE iso_week >= $1 AND concept != '_all' GROUP BY concept""", since_week)}
    fams = defaultdict(list)
    for r in rows:
        fams[r["family"]].append({"concept": r["concept"], "label_en": r["label_en"],
                                  "pattern": r["pattern"], "n": tot.get(r["concept"], 0)})
    order = [f for f in FAMILIES if f in fams] + sorted(f for f in fams if f not in FAMILIES)
    return [{"family": f, "label": FAMILY_LABELS.get(f, f), "concepts": fams[f]} for f in order]


async def get_series(db, concept, weeks):
    """Rows = weeks newest first, cells = speakers: docs, denom, rate, thin."""
    since = weeks[-1][0]
    rows = await db.fetch(
        """SELECT concept, speaker, iso_week, docs, denom FROM discourse_weekly
           WHERE concept IN ($1, '_all') AND iso_week >= $2""", concept, since)
    hit, den = {}, {}
    for r in rows:
        if r["concept"] == ALL:
            den[(r["speaker"], r["iso_week"])] = r["denom"]
        else:
            hit[(r["speaker"], r["iso_week"])] = r["docs"]
    out_weeks = []
    col_max = defaultdict(float)
    totals = {sp: {"docs": 0, "denom": 0} for sp in SPEAKERS}
    for i, (wk, monday) in enumerate(weeks):
        cells = {}
        for sp in SPEAKERS:
            d, n = hit.get((sp, wk), 0), den.get((sp, wk), 0)
            r_ = rate(d, n)
            cells[sp] = {"docs": d, "denom": n, "rate": r_, "thin": n < THIN}
            totals[sp]["docs"] += d
            totals[sp]["denom"] += n
            if r_ and not cells[sp]["thin"]:
                col_max[sp] = max(col_max[sp], r_)
        out_weeks.append({"iso_week": wk, "week_start": monday, "is_current": i == 0,
                          "cells": cells})
    for w in out_weeks:          # bar width scaled per speaker: one small multiple each
        for sp, c in w["cells"].items():
            m = col_max.get(sp) or 0
            c["bar"] = int(round(100 * min(c["rate"] or 0, m) / m)) if m else 0
    for sp, t in totals.items():
        t["rate"] = rate(t["docs"], t["denom"])
    return {"weeks": out_weeks, "totals": totals}


async def get_new_this_week(db, weeks_all):
    """Concept x speaker cells whose count in the reference week (the last COMPLETE
    week) jumps against the trailing TRAIL-week mean: docs >= JUMP_MIN and
    docs >= JUMP_RATIO x mean. Also flags first appearances (zero in the trailing
    window, and, separately, the first week ever in the table). Denominators for
    the week and the trailing mean are returned so a crawl-volume jump is visible."""
    ref, ref_monday = weeks_all[1]
    trail = [w for w, _ in weeks_all[2:2 + TRAIL]]
    lo = trail[-1]
    rows = await db.fetch(
        """SELECT concept, speaker, iso_week, docs, denom FROM discourse_weekly
           WHERE iso_week >= $1 AND iso_week <= $2""", lo, ref)
    cur, prev, den_cur, den_prev = {}, defaultdict(int), {}, defaultdict(int)
    for r in rows:
        k = (r["concept"], r["speaker"])
        if r["concept"] == ALL:
            if r["iso_week"] == ref:
                den_cur[r["speaker"]] = r["denom"]
            else:
                den_prev[r["speaker"]] += r["denom"]
            continue
        if r["iso_week"] == ref:
            cur[k] = r["docs"]
        else:
            prev[k] += r["docs"]
    cand = [k for k in cur if not prev.get(k)]
    first_ever = set()
    if cand:
        concepts = sorted({c for c, _ in cand})
        q = ("SELECT concept, speaker, MIN(iso_week) AS w0 FROM discourse_weekly WHERE concept IN ("
             + ",".join(f"${i + 1}" for i in range(len(concepts))) + ") GROUP BY concept, speaker")
        for r in await db.fetch(q, *concepts):
            if r["w0"] == ref:
                first_ever.add((r["concept"], r["speaker"]))
    items = []
    for (c, sp), d in cur.items():
        mean = prev.get((c, sp), 0) / TRAIL
        is_first = mean == 0
        jump = d >= JUMP_MIN and d >= JUMP_RATIO * mean
        if not (jump or is_first):
            continue
        dn = den_cur.get(sp, 0)
        dmean = den_prev.get(sp, 0) / TRAIL
        items.append({
            "concept": c, "speaker": sp, "speaker_label": SPEAKER_LABELS.get(sp, sp),
            "docs": d, "trail_mean": round(mean, 2), "denom": dn, "denom_mean": round(dmean, 1),
            "rate": rate(d, dn), "trail_rate": rate(prev.get((c, sp), 0), den_prev.get(sp, 0)),
            "kind": "first_ever" if (c, sp) in first_ever else ("first_in_window" if is_first else "jump"),
            "ratio": round(d / mean, 1) if mean else None,
            "volume_driven": bool(dmean and dn >= JUMP_RATIO * dmean),
        })
    order = {"first_ever": 0, "jump": 1, "first_in_window": 2}
    # Volume-driven cells sort last: on 2026-11-12 business press output was 882 docs
    # in 2026-W45 against a trailing mean of 108 (the finmedia crawl arriving), so
    # every term it carried looked "new". They stay listed, tagged, below the rest.
    items.sort(key=lambda x: (x["volume_driven"], order[x["kind"]], -x["docs"],
                              -(x["ratio"] or 0), x["concept"]))
    return {"ref_week": ref, "ref_monday": ref_monday, "trail_from": lo, "trail_to": trail[0],
            "rows": items[:NEW_LIMIT], "n_items": len(items)}


async def get_discourse(db, concept: str = DEFAULT_CONCEPT, weeks=DEFAULT_WEEKS):
    """Assemble the /discourse page; None when the tables are absent."""
    if not await tables_present(db):
        return None
    n = clamp_weeks(weeks)
    key = ("page", concept, n)
    hit = _cached(key)
    if hit is not None:
        return hit
    wk = recent_weeks(n)
    families = await get_concepts(db, wk[-1][0])
    known = {c["concept"]: c for f in families for c in f["concepts"]}
    if concept not in known:
        concept = DEFAULT_CONCEPT if DEFAULT_CONCEPT in known else next(iter(known), concept)
    data = {
        "concept": concept, "info": known.get(concept, {}), "weeks": n,
        "families": families,
        "speakers": [{"key": s, "label": SPEAKER_LABELS[s], "media": s in MEDIA_SPEAKERS} for s in SPEAKERS],
        "series": await get_series(db, concept, wk),
        "new": await get_new_this_week(db, recent_weeks(TRAIL + 2)),
        "this_week": wk[0][0], "thin": THIN, "trail": TRAIL,
        "jump_min": JUMP_MIN, "jump_ratio": JUMP_RATIO,
    }
    return _store(key, data)
