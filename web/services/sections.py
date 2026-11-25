"""Section coverage for /admin/sections.

Reads ONLY precomputed data, so the page renders in milliseconds:

* ``section_registry`` / ``section_registry_meta`` — built nightly by
  ``scripts/build_section_registry.py`` from the crawler code joined to the corpus
  (what each crawler is configured to crawl, and what we hold per section);
* ``data/known_missing_sections.yaml`` — the explicit, hand-kept list of sections we
  know a site HAS and we do not crawl (status: missing | added | blocked | broken).

The two are deliberately separate. The registry can only describe what a crawler
declares, so it cannot know about a section nobody configured; the YAML is where a
person (or an audit) records that gap. Nothing here scans ``documents``.
"""
from __future__ import annotations

import time
from pathlib import Path

import yaml

KNOWN_MISSING_PATH = Path(__file__).resolve().parents[2] / "data" / "known_missing_sections.yaml"
STATUSES = ("missing", "broken", "blocked", "added")
_cache: dict = {"mtime": None, "data": None}

LEVELS = ("central", "provincial", "municipal", "district", "department", "media", "research")


def load_known_missing(path: Path = KNOWN_MISSING_PATH) -> dict[str, list[dict]]:
    """-> {site_key: [entry, ...]}. Cached on the file's mtime. A malformed entry is
    kept and labelled rather than dropped: a gap list that silently loses rows is the
    failure this page exists to prevent."""
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return {}
    if _cache["mtime"] == mtime and _cache["data"] is not None:
        return _cache["data"]
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, list[dict]] = {}
    for e in raw.get("sections", []) or []:
        if not isinstance(e, dict) or not e.get("site_key"):
            continue
        st = str(e.get("status", "missing"))
        out.setdefault(str(e["site_key"]), []).append({
            "site_key": str(e["site_key"]),
            "name": str(e.get("name", "")),
            "path": str(e.get("path", "")),
            "example_url": str(e.get("example_url", "")),
            "status": st if st in STATUSES else f"invalid:{st}",
            "note": str(e.get("note", "")),
            "found": str(e.get("found", "")),
        })
    _cache.update(mtime=mtime, data=out)
    return out


async def get_sections(db, level: str = "central", site: str = "", issues_only: bool = False) -> dict:
    """Everything the template needs. `level=''` means every admin level."""
    t0 = time.time()
    missing = load_known_missing()
    try:
        meta = {r["k"]: r["v"] for r in await db.fetch("SELECT k, v FROM section_registry_meta")}
        where, args = [], []
        if site:
            where.append(f"site_key = ${len(args) + 1}")
            args.append(site)
        elif level:
            where.append(f"admin_level = ${len(args) + 1}")
            args.append(level)
        sql = "SELECT * FROM section_registry"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY site_key, rowid"
        rows = [dict(r) for r in await db.fetch(sql, *args)]
        built = True
    except Exception:           # table not built yet (fresh DB, or before first nightly)
        meta, rows, built = {}, [], False

    sites: dict[str, dict] = {}
    for r in rows:
        s = sites.setdefault(r["site_key"], {
            "site_key": r["site_key"], "site": None, "sections": [], "observed": [],
            "unattributed": None, "unknown": None, "missing": missing.get(r["site_key"], []),
        })
        kind = r["kind"]
        if kind == "site":
            s["site"] = r
        elif kind == "section":
            s["sections"].append(r)
        elif kind == "observed":
            s["observed"].append(r)
        elif kind == "unattributed":
            s["unattributed"] = r
        elif kind == "unknown":
            s["unknown"] = r

    # Sites that have a known-missing entry but no registry row under this filter
    # still have to show: the gap list must never be hidden by a filter miss.
    if not site and not level:
        for sk, entries in missing.items():
            sites.setdefault(sk, {"site_key": sk, "site": None, "sections": [], "observed": [],
                                  "unattributed": None, "unknown": None, "missing": entries})

    out = []
    for s in sites.values():
        secs = s["sections"]
        open_gaps = [m for m in s["missing"] if m["status"] != "added"]
        s["n_stale"] = sum(1 for x in secs if x["staleness"] == "stale")
        s["n_empty"] = sum(1 for x in secs if not x["docs"])
        s["n_open_gaps"] = len(open_gaps)
        sched = (s["site"] or {}).get("schedule", "")
        s["has_issue"] = bool(s["n_stale"] or s["n_empty"] or open_gaps or s["unknown"]
                              or sched == "not scheduled"
                              or (s["site"] or {}).get("staleness") == "stale")
        if issues_only and not s["has_issue"]:
            continue
        out.append(s)
    out.sort(key=lambda s: (-s["n_open_gaps"], -((s["site"] or {}).get("docs") or 0)))

    all_missing = [m for entries in missing.values() for m in entries]
    return {
        "built": built, "meta": meta, "sites": out,
        "level": level, "site": site, "issues_only": issues_only, "levels": LEVELS,
        "missing_counts": {st: sum(1 for m in all_missing if m["status"] == st) for st in STATUSES},
        "render_ms": round((time.time() - t0) * 1000, 1),
    }
