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


async def get_annotation(db, slug):
    a = _get(slug)
    if not a:
        return None
    items = []
    for it in a.get("items", []):
        q = it.get("queries", {})
        mentions = []
        for m in q.get("mentions", []):
            n = await _count(db, term=m.get("term"), term_all=m.get("term_all"))
            mentions.append({"label": m["label"], "count": n})
        breakdown = await _breakdown(db, q["breakdown"]) if q.get("breakdown") else None
        linked = await _linked(db, q["linked"]) if q.get("linked") else []
        for d in linked:
            d["src"] = _src(d["site_key"])
        top_rank = max((d["rank"] for d in linked), default=0)
        items.append({
            "id": it["id"], "index_label": it.get("index_label", it["id"]),
            "path": it.get("path", []), "heading_cn": it["heading_cn"],
            "heading_en": it.get("heading_en", ""), "subhead": it.get("subhead", ""),
            "clauses": [{"num": c["num"], "parts": _parse_marks(c["text"]),
                         "gloss": c.get("gloss", "")} for c in it.get("clauses", [])],
            "mentions": mentions, "breakdown": breakdown, "linked": linked,
            "linked_count": len(linked), "top_rank": top_rank,
            "reading": (it.get("reading") or "").strip(),
        })
    return {
        "slug": a["slug"], "doc_number": a.get("doc_number", ""),
        "title_cn": a.get("title_cn", ""), "title_en": a.get("title_en", ""),
        "date": a.get("date", ""), "items": items,
    }
