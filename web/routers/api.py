"""JSON API routes.

All endpoints are prefixed with /api/v1 (see app.py).
Responses are JSON dicts; list endpoints include pagination metadata.
"""
from fastapi import APIRouter, Request, Query
from web.services.documents import (
    get_documents, get_document, get_document_citations,
    get_sites, get_stats, search_documents, get_categories,
    REF_PATTERN, get_admin_level,
)

router = APIRouter()


@router.get("/documents")
async def api_documents(
    request: Request,
    site: str = None, category: str = None, year: int = None,
    has_docnum: bool = None, page: int = 1, per_page: int = 50,
):
    """Paginated document listing with optional filters by site, category, year, and doc-number presence."""
    db = request.app.state.db
    rows, total = await get_documents(db, site, category, year, has_docnum, page, per_page)
    return {"documents": [dict(r) for r in rows], "total": total, "page": page}


@router.get("/documents/{doc_id}")
async def api_document(request: Request, doc_id: int):
    """Single document by ID. Returns all columns including body_text_cn."""
    db = request.app.state.db
    doc = await get_document(db, doc_id)
    if not doc:
        return {"error": "not found"}
    return dict(doc)


@router.get("/documents/{doc_id}/citations")
async def api_citations(request: Request, doc_id: int):
    """Forward and reverse citations for a document (cites / cited_by)."""
    db = request.app.state.db
    cites, cited_by = await get_document_citations(db, doc_id)
    return {"cites": cites, "cited_by": cited_by}


@router.get("/search")
async def api_search(request: Request, q: str = "", page: int = 1):
    """Full-text search across title, document_number, keywords, abstract, and body."""
    if not q:
        return {"results": [], "total": 0}
    db = request.app.state.db
    rows, total = await search_documents(db, q, page)
    return {"results": [dict(r) for r in rows], "total": total, "page": page}


@router.get("/sites")
async def api_sites(request: Request):
    """All crawled sites with document counts and body-text coverage."""
    db = request.app.state.db
    rows = await get_sites(db)
    return {"sites": [dict(r) for r in rows]}


@router.get("/stats")
async def api_stats(request: Request):
    """Corpus-wide statistics: totals, body-text coverage, and documents by year."""
    db = request.app.state.db
    return await get_stats(db)


@router.get("/categories")
async def api_categories(request: Request):
    """Distinct document categories with counts (from gkmlpt classify_main_name)."""
    db = request.app.state.db
    rows = await get_categories(db)
    return {"categories": [dict(r) for r in rows]}


@router.get("/network")
async def api_network(request: Request, site: str = None, min_degree: int = 2):
    """Citation network as nodes + edges for D3.js."""
    db = request.app.state.db

    if site:
        rows = await db.fetch(
            "SELECT id, title, document_number, site_key, body_text_cn, publisher "
            "FROM documents WHERE body_text_cn != '' AND site_key = $1", site
        )
    else:
        rows = await db.fetch(
            "SELECT id, title, document_number, site_key, body_text_cn, publisher "
            "FROM documents WHERE body_text_cn != ''"
        )

    # Build known docs lookup
    all_docs = await db.fetch(
        "SELECT id, document_number, title, site_key FROM documents WHERE document_number != ''"
    )
    known = {r["document_number"]: dict(r) for r in all_docs}

    raw_edges = []  # (source_docnum, target_docnum, source_id)
    node_refs = {}  # docnum -> citation count

    for row in rows:
        refs = REF_PATTERN.findall(row["body_text_cn"])
        if not refs:
            continue
        src = row["document_number"]
        for ref in refs:
            node_refs[ref] = node_refs.get(ref, 0) + 1
            if src:  # only create edges from docs with a document_number
                raw_edges.append((src, ref, row["id"]))

    # Filter by min degree
    frequent = {ref for ref, cnt in node_refs.items() if cnt >= min_degree}

    # Build node set — include frequent cited docs + source docs that cite them
    node_set = set(frequent)
    for src, tgt, _ in raw_edges:
        if tgt in frequent:
            node_set.add(src)

    # Build node list
    nodes = []
    for ref in node_set:
        level = get_admin_level(ref)
        resolved = known.get(ref)
        nodes.append({
            "id": ref, "label": ref, "level": level,
            "citations": node_refs.get(ref, 0),
            "title": resolved["title"] if resolved else "",
            "resolved": bool(resolved),
        })

    # Filter edges to only include nodes in the graph
    edges = [
        {"source": src, "target": tgt, "source_id": sid}
        for src, tgt, sid in raw_edges
        if src in node_set and tgt in node_set
    ]

    return {"nodes": nodes, "edges": edges}
