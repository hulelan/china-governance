"""Topical document collections (e.g. the oil / petroleum-policy watch).

A collection is defined by a live corpus query plus a curated annotation layer
(data/collections/<slug>.json: per-URL theme/focus-tag/English gloss/significance
note, + the source-tier hierarchy). Documents are pulled fresh from documents.db
each request so the page stays current; annotations are overlaid by URL. New docs
matching the query that aren't yet annotated still appear (auto-classified).
"""
import json
import re
from pathlib import Path

_DIR = Path(__file__).parent.parent.parent / "data" / "collections"
_CACHE = {}

# Two live queries define the oil collection (mirrors the analysis that built it):
# (A) oil/petroleum POLICY docs by title; (B) the reserves / Iran-War import posture set.
# Titles are short, so title LIKE stays cheap; the only BODY-text condition (the
# ≥3-char reserve terms) is routed through the FTS5 trigram index instead of a
# full body scan (which would reintroduce the ~6s slowness we just removed).
_SINCE = "2026-02-01"
_POLICY_WHERE = (
    "(d.title LIKE '%石油%' OR d.title LIKE '%原油%' OR d.title LIKE '%油气%' "
    "OR d.title LIKE '%成品油%' OR d.title LIKE '%炼油%')")
_RESERVE_BODY_FTS = (
    "d.id IN (SELECT rowid FROM doc_search "
    "WHERE doc_search MATCH '\"战略石油储备\" OR \"原油储备\"')")
_RESERVE_BODY_LIKE = (
    "(d.body_text_cn LIKE '%战略石油储备%' OR d.body_text_cn LIKE '%原油储备%')")


def _focus_where(reserve_body):
    return (
        "(d.title LIKE '%石油储备%' OR d.title LIKE '%原油储备%' "
        f"OR {reserve_body} "
        "OR ((d.title LIKE '%伊朗%' OR d.title LIKE '%霍尔木兹%' OR d.title LIKE '%原油%' "
        "     OR d.title LIKE '%油价%' OR d.title LIKE '%石油%') "
        "    AND (d.title LIKE '%进口%' OR d.title LIKE '%采购%' OR d.title LIKE '%抢购%' "
        "         OR d.title LIKE '%储备%' OR d.title LIKE '%霍尔木兹%' OR d.title LIKE '%供应%')))")

_SNIPPET = ("substr(replace(replace(replace(body_text_cn, char(10), ' '), "
            "char(13), ' '), char(9), ' '), 1, 260)")


def _load(slug):
    if slug not in _CACHE:
        with (_DIR / f"{slug}.json").open(encoding="utf-8") as f:
            _CACHE[slug] = json.load(f)
    return _CACHE[slug]


def _tier_for(site, admin_level, sites_cfg):
    if site in sites_cfg:
        return sites_cfg[site]["tier"]
    return {"central": "central", "provincial": "provincial",
            "municipal": "municipal", "district": "municipal"}.get(admin_level, "news")


def _ftag_of(title):
    if "储备" in title: return "reserve"
    if "霍尔木兹" in title: return "hormuz"
    if any(k in title for k in ("中方", "外交部", "中国", "中企")): return "chinaresp"
    if any(k in title for k in ("进口", "采购", "抢购", "供应")): return "import"
    return "hormuz"


def _china(t):
    return any(k in t for k in ("中国", "中方", "外交部", "中企", "独立炼油", "人民币"))


_payload_cache = {}  # slug -> (monotonic_ts, payload). Collection changes only when
_CACHE_TTL = 1800    # new docs are crawled (nightly), so a 30-min cache is safe.


async def get_collection(db, slug="oil"):
    """Return the render payload for a topical collection (cached ~30 min).

    The title conditions are 2-char terms that can't use the trigram index, so the
    live query is ~3s; caching makes repeat loads instant. The nightly restart
    clears the cache, picking up newly-crawled docs.
    """
    import time
    hit = _payload_cache.get(slug)
    if hit and (time.monotonic() - hit[0]) < _CACHE_TTL:
        return hit[1]
    payload = await _build_collection(db, slug)
    _payload_cache[slug] = (time.monotonic(), payload)
    return payload


async def _build_collection(db, slug="oil"):
    """Return the render payload for a topical collection."""
    cfg = _load(slug)
    sites_cfg = cfg["config"]["sites"]
    ann = cfg["annotations"]
    ftags = set(cfg["config"]["ftags"].keys())

    cols = (f"d.date_published AS date, d.site_key AS site, d.title, d.url, "
            f"s.name AS src_name, s.admin_level, {_SNIPPET} AS snippet")

    async def q(where):
        return await db.fetch(
            f"""SELECT {cols} FROM documents d
                LEFT JOIN sites s ON d.site_key = s.site_key
                WHERE {where} AND d.date_published >= '{_SINCE}'""")

    from web.services.documents import _fts_available
    reserve_body = _RESERVE_BODY_FTS if await _fts_available(db) else _RESERVE_BODY_LIKE
    policy_rows = await q(_POLICY_WHERE)
    focus_rows = await q(_focus_where(reserve_body))

    by_url = {}
    for rows, in_policy, in_focus in ((policy_rows, True, False), (focus_rows, False, True)):
        for r in rows:
            r = dict(r)
            u = r["url"]
            if not u:
                continue
            if u in by_url:
                by_url[u]["in_policy"] |= in_policy
                by_url[u]["in_focus"] |= in_focus
                continue
            site = r["site"]
            scfg = sites_cfg.get(site)
            a = ann.get(u, {})
            theme = a.get("theme") or "geo"
            ftag = a.get("ftag") or (_ftag_of(r["title"]) if in_focus else (theme if theme in ftags else ""))
            by_url[u] = {
                "date": (r["date"] or "")[:10], "site": site,
                "src_cn": (scfg["cn"] if scfg else (r.get("src_name") or site)),
                "src_en": (scfg["en"] if scfg else (r.get("src_name") or site)),
                "tier": _tier_for(site, r.get("admin_level"), sites_cfg),
                "title": r["title"], "url": u, "snippet": (r.get("snippet") or "").strip(),
                "theme": theme, "ftag": ftag, "en": a.get("en", ""), "note": a.get("note", ""),
                "in_policy": in_policy, "in_focus": in_focus, "china": _china(r["title"]),
            }

    docs = sorted(by_url.values(), key=lambda x: x["date"], reverse=True)
    srcN, months = {}, {}
    for o in docs:
        srcN[o["site"]] = srcN.get(o["site"], 0) + 1
        if o["date"]:
            months[o["date"][:7]] = months.get(o["date"][:7], 0) + 1

    # sources present, ranked by tier; fill display names for any not in the cfg
    sites_out = {}
    for site, n in srcN.items():
        scfg = sites_cfg.get(site)
        tier = _tier_for(site, next((d["tier"] for d in docs if d["site"] == site), None), sites_cfg) \
            if not scfg else scfg["tier"]
        sites_out[site] = {
            "cn": scfg["cn"] if scfg else next((d["src_cn"] for d in docs if d["site"] == site), site),
            "en": scfg["en"] if scfg else site,
            "tier": next(d["tier"] for d in docs if d["site"] == site), "n": n}

    return {
        "docs": docs, "sites": sites_out,
        "tierRank": cfg["config"]["tierRank"], "tierLabel": cfg["config"]["tierLabel"],
        "themes": cfg["config"]["themes"], "ftags": cfg["config"]["ftags"],
        "months": months,
        "counts": {"all": len(docs),
                   "policy": sum(o["in_policy"] for o in docs),
                   "focus": sum(o["in_focus"] for o in docs),
                   "china": sum(o["china"] for o in docs)},
    }
