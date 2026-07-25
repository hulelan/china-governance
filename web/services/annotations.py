"""Annotations service — annotated readings of policy documents.

Loads data/annotations.yaml (curation: clause text, queries, reading slot) and
computes every displayed NUMBER live from the corpus: mention counts, the
"where mentioned" source breakdown, and the linked-document catalog. Nothing is
invented — each figure traces to a query in the YAML.
"""
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).parent.parent.parent / "data" / "annotations.yaml"
_CACHED = None
NONE = "__none__"   # aiplus_map sentinel for docs that map to no specific item


def _load():
    global _CACHED
    if _CACHED is None:
        with _YAML_PATH.open(encoding="utf-8") as f:
            _CACHED = yaml.safe_load(f)
    return _CACHED


def list_annotations() -> list:
    """Return annotation summaries for the hub index (no DB needed)."""
    out = []
    for a in _load().get("annotations", []):
        out.append({
            "slug": a["slug"], "doc_number": a.get("doc_number", ""),
            "title_cn": a.get("title_cn", ""), "title_en": a.get("title_en", ""),
            "date": a.get("date", ""), "item_count": len(a.get("items", [])),
            "items": [{"id": it["id"], "heading_cn": it["heading_cn"],
                       "heading_en": it.get("heading_en", "")}
                      for it in a.get("items", [])],
        })
    return out


def _get(slug):
    for a in _load().get("annotations", []):
        if a["slug"] == slug:
            return a
    return None


def _parse_marks(text: str):
    """Split verbatim clause text on {…} highlight markers → list of (text, is_mark)."""
    parts, buf, mark = [], "", False
    i = 0
    while i < len(text):
        c = text[i]
        if c == "{":
            if buf:
                parts.append((buf, mark)); buf = ""
            mark = True
        elif c == "}":
            if buf:
                parts.append((buf, mark)); buf = ""
            mark = False
        else:
            buf += c
        i += 1
    if buf:
        parts.append((buf, mark))
    return parts


async def _count(db, term=None, term_all=None):
    if term_all:
        conds = " AND ".join(f"body_text_cn LIKE ${i+1}" for i in range(len(term_all)))
        args = [f"%{t}%" for t in term_all]
        return await db.fetchval(f"SELECT COUNT(*) FROM documents WHERE {conds}", *args)
    return await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE body_text_cn LIKE $1", f"%{term}%")


async def _breakdown(db, term):
    rows = await db.fetch(
        "SELECT site_key, COUNT(*) c FROM documents WHERE body_text_cn LIKE $1 "
        "GROUP BY site_key ORDER BY c DESC", f"%{term}%")
    total = sum(r[1] for r in rows)
    top = rows[:8]
    mx = top[0][1] if top else 1
    return {"total": total, "n_sources": len(rows), "shown": len(top),
            "rows": [{"site_key": r[0], "count": r[1], "src": _src(r[0]),
                      "pct": round(r[1] / mx * 100)} for r in top]}


async def _linked_from_map(db, taxonomy_id, limit=12):
    """Linked docs from the DeepSeek AI+ mapping (aiplus_map), by citation-rank."""
    rows = await db.fetch(
        "SELECT d.id, d.site_key, d.title, substr(COALESCE(d.date_published,''),1,10) dt, "
        "d.citation_rank FROM aiplus_map m JOIN documents d ON d.id = m.doc_id "
        "WHERE m.item_id = $1 AND d.title != '' "
        "ORDER BY d.citation_rank DESC, d.date_published DESC LIMIT $2",
        taxonomy_id, limit)
    return [{"id": r[0], "site_key": r[1], "title": r[2], "date": r[3],
             "rank": round(r[4] or 0, 1)} for r in rows]


async def _map_count(db, taxonomy_id):
    return await db.fetchval(
        "SELECT COUNT(*) FROM aiplus_map WHERE item_id = $1", taxonomy_id)


async def _linked(db, spec):
    ors, args, i = [], [], 1
    for t in spec.get("title_any", []):
        ors.append(f"title LIKE ${i}"); args.append(f"%{t}%"); i += 1
    for a, b in spec.get("title_all_pairs", []):
        ors.append(f"(title LIKE ${i} AND title LIKE ${i+1})")
        args += [f"%{a}%", f"%{b}%"]; i += 2
    where = "(" + " OR ".join(ors) + ")" if ors else "1=1"
    where += f" AND citation_rank >= ${i}"; args.append(spec.get("min_rank", 0)); i += 1
    limit = int(spec.get("limit", 12))
    rows = await db.fetch(
        f"SELECT id, site_key, title, substr(COALESCE(date_published,''),1,10) d, "
        f"citation_rank FROM documents WHERE {where} AND title != '' "
        f"GROUP BY title ORDER BY citation_rank DESC LIMIT {limit}", *args)
    return [{"id": r[0], "site_key": r[1], "title": r[2], "date": r[3],
             "rank": round(r[4] or 0, 1)} for r in rows]


# site_key → display source name + admin level (for badges). Falls back to key.
_SRC = {
    "gov": ("国务院", "central"), "ndrc": ("发改委", "central"), "cac": ("网信办", "central"),
    "miit": ("工信部", "central"), "most": ("科技部", "central"), "mof": ("财政部", "central"),
    "stdaily": ("科技日报", "media"), "xinhua": ("新华社", "media"), "people": ("人民日报", "media"),
    "guancha": ("观察者网", "media"), "cppcc": ("全国政协", "central"), "stic": ("深圳", "municipal"),
    "gd": ("广东", "provincial"), "elsewhere": ("别处", "media"),
}


def _src(site_key):
    name, level = _SRC.get(site_key, (site_key, "central"))
    return {"name": name, "level": level}


_TAXO_PATH = Path(__file__).parent.parent.parent / "data" / "aiplus_taxonomy.yaml"
_TAXO = None


def _load_taxonomy():
    global _TAXO
    if _TAXO is None:
        with _TAXO_PATH.open(encoding="utf-8") as f:
            _TAXO = yaml.safe_load(f)["items"]
    return _TAXO


def _meta(a):
    return {"slug": a["slug"], "doc_number": a.get("doc_number", ""),
            "title_cn": a.get("title_cn", ""), "title_en": a.get("title_en", ""),
            "date": a.get("date", "")}


async def _build_curated_item(db, it):
    q = it.get("queries", {})
    mentions = []
    for m in q.get("mentions", []):
        n = await _count(db, term=m.get("term"), term_all=m.get("term_all"))
        mentions.append({"label": m["label"], "count": n})
    breakdown = await _breakdown(db, q["breakdown"]) if q.get("breakdown") else None
    tax_id = it.get("taxonomy_id")
    if q.get("linked"):                               # hand-curated keyword query wins
        linked = await _linked(db, q["linked"]); linked_count = len(linked)
    elif tax_id:                                      # else the DeepSeek map
        linked = await _linked_from_map(db, tax_id, 12); linked_count = await _map_count(db, tax_id)
    else:
        linked, linked_count = [], 0
    for d in linked:
        d["src"] = _src(d["site_key"])
    return {
        "id": it.get("taxonomy_id") or it["id"], "index_label": it.get("index_label", it["id"]),
        "path": it.get("path", []), "heading_cn": it["heading_cn"],
        "heading_en": it.get("heading_en", ""), "subhead": it.get("subhead", ""),
        "clauses": [{"num": c["num"], "parts": _parse_marks(c["text"]), "gloss": c.get("gloss", "")}
                    for c in it.get("clauses", [])],
        "mentions": mentions, "breakdown": breakdown, "linked": linked,
        "linked_count": linked_count, "top_rank": max((d["rank"] for d in linked), default=0),
        "reading": (it.get("reading") or "").strip(), "curated": True,
    }


async def _build_taxo_item(db, t):
    linked = await _linked_from_map(db, t["id"], 24)
    for d in linked:
        d["src"] = _src(d["site_key"])
    count = await _map_count(db, t["id"])
    return {
        "id": t["id"], "index_label": t["id"], "path": [t["group"], t["cn"]],
        "heading_cn": t["cn"], "heading_en": t["en"], "subhead": t["group"] + " · mapped from the corpus",
        "clauses": [], "mentions": [], "breakdown": None, "linked": linked,
        "linked_count": count, "top_rank": max((d["rank"] for d in linked), default=0),
        "reading": "", "curated": False,
    }


async def get_overview(db, slug):
    """Coverage map: every taxonomy item + its live document count from the map."""
    a = _get(slug)
    if not a:
        return None
    taxo = _load_taxonomy()
    rows = await db.fetch("SELECT item_id, COUNT(*) c FROM aiplus_map "
                          "WHERE item_id != $1 GROUP BY item_id", NONE)
    counts = {r[0]: r[1] for r in rows}
    none_count = await db.fetchval("SELECT COUNT(*) FROM aiplus_map WHERE item_id = $1", NONE)
    total_tagged = await db.fetchval(
        "SELECT COUNT(DISTINCT doc_id) FROM aiplus_map WHERE item_id != $1", NONE)
    curated_ids = {it.get("taxonomy_id") for it in a.get("items", []) if it.get("taxonomy_id")}
    maxc = max(counts.values(), default=1)
    order, gmap = [], {}
    for t in taxo:
        g = t["group"]
        if g not in gmap:
            gmap[g] = []; order.append(g)
        c = counts.get(t["id"], 0)
        gmap[g].append({"id": t["id"], "cn": t["cn"], "en": t["en"], "count": c,
                        "pct": round(c / maxc * 100), "curated": t["id"] in curated_ids})
    groups = [{"name": g, "items": gmap[g]} for g in order]
    return {**_meta(a), "groups": groups, "maxc": maxc, "n_items": len(taxo),
            "total_tagged": total_tagged, "none_count": none_count}


async def get_item(db, slug, item_id):
    """One item detail: curated (clauses/reading) if authored, else the mapped docs."""
    a = _get(slug)
    if not a:
        return None
    for it in a.get("items", []):
        if it.get("taxonomy_id") == item_id or it.get("id") == item_id:
            return {"annotation": _meta(a), "item": await _build_curated_item(db, it)}
    t = next((x for x in _load_taxonomy() if x["id"] == item_id), None)
    if not t:
        return None
    return {"annotation": _meta(a), "item": await _build_taxo_item(db, t)}
