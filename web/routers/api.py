"""JSON API routes.

All endpoints are prefixed with /api/v1 (see app.py).
Responses are JSON dicts; list endpoints include pagination metadata.
"""
from fastapi import APIRouter, Request, Query
from web.services.documents import (
    get_documents, get_document, get_document_citations,
    get_sites, get_stats, search_documents, get_categories,
    get_citation_neighborhood, date_str_to_timestamp,
    REF_PATTERN, get_admin_level,
)
from web.services.inbox import get_inbox_dates, get_documents_for_date

router = APIRouter()


@router.get("/documents")
async def api_documents(
    request: Request,
    site: str = None, category: str = None, year: int = None,
    has_docnum: bool = None, page: int = 1, per_page: int = 50,
    date_start: str = None, date_end: str = None,
    importance: str = None,
):
    """Paginated document listing with optional filters by site, category, year, date range, importance, and doc-number presence."""
    db = request.app.state.db
    ds = date_str_to_timestamp(date_start) if date_start else None
    de = date_str_to_timestamp(date_end) if date_end else None
    rows, total = await get_documents(db, site, category, year, has_docnum, page, per_page,
                                      date_start=ds, date_end=de, importance=importance)
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


@router.get("/documents/{doc_id}/network")
async def api_doc_network(request: Request, doc_id: int):
    """1-hop citation neighborhood graph for a single document (nodes + edges for D3.js)."""
    db = request.app.state.db
    return await get_citation_neighborhood(db, doc_id)


@router.get("/search")
async def api_search(request: Request, q: str = "", page: int = 1,
                     date_start: str = None, date_end: str = None):
    """Full-text search across title, document_number, keywords, abstract, and body."""
    if not q:
        return {"results": [], "total": 0}
    db = request.app.state.db
    ds = date_str_to_timestamp(date_start) if date_start else None
    de = date_str_to_timestamp(date_end) if date_end else None
    rows, total = await search_documents(db, q, page, date_start=ds, date_end=de)
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


@router.get("/inbox")
async def api_inbox(request: Request, site: str = None, admin_level: str = None,
                    date: int = None):
    """Inbox data: date groups with counts, or documents for a specific date."""
    db = request.app.state.db
    if date:
        docs = await get_documents_for_date(db, date, site_key=site, admin_level=admin_level)
        return {"documents": [dict(r) for r in docs]}
    dates = await get_inbox_dates(db, site_key=site, admin_level=admin_level)
    return {"dates": dates}


@router.get("/network")
async def api_network(request: Request, site: str = None, min_degree: int = 2,
                      date_start: str = None, date_end: str = None,
                      doc_type: str = None):
    """Citation network as nodes + edges for D3.js, using pre-computed citations table."""
    db = request.app.state.db
    ds = date_str_to_timestamp(date_start) if date_start else None
    de = date_str_to_timestamp(date_end) if date_end else None

    # Build source filter for citations (filter by source doc attributes)
    source_where = ["sd.document_number != ''"]
    source_params = []
    idx = 1  # $1 is min_degree
    if site:
        idx += 1
        source_where.append(f"sd.site_key = ${idx}")
        source_params.append(site)
    if ds is not None:
        idx += 1
        source_where.append(f"sd.date_written >= ${idx}")
        source_params.append(ds)
    if de is not None:
        idx += 1
        source_where.append(f"sd.date_written < ${idx}")
        source_params.append(de)
    if doc_type == "_untyped":
        source_where.append("(sd.algo_doc_type IS NULL OR sd.algo_doc_type = '' OR sd.algo_doc_type = 'other')")
    elif doc_type:
        idx += 1
        source_where.append(f"sd.algo_doc_type = ${idx}")
        source_params.append(doc_type)

    source_filter = " AND ".join(source_where)

    # Get citation counts filtered by source doc attributes
    cite_rows = await db.fetch(f"""
        SELECT c.target_ref, COUNT(*) as cnt, c.target_level
        FROM citations c
        JOIN documents sd ON sd.id = c.source_id
        WHERE {source_filter}
        GROUP BY c.target_ref
        HAVING cnt >= $1
    """, min_degree, *source_params)

    frequent = {r["target_ref"]: {"count": r["cnt"], "level": r["target_level"]} for r in cite_rows}

    if not frequent:
        return {"nodes": [], "edges": []}

    # Get edges involving frequent nodes (with same source filter)
    edge_rows = await db.fetch(f"""
        SELECT c.source_id, c.target_ref,
               sd.document_number as source_docnum
        FROM citations c
        JOIN documents sd ON sd.id = c.source_id
        WHERE {source_filter}
    """, min_degree, *source_params)  # min_degree not used but keeps param indices consistent

    # Build node set and filtered edges
    node_set = set(frequent.keys())
    raw_edges = []
    for r in edge_rows:
        tgt = r["target_ref"]
        src = r["source_docnum"]
        if tgt in frequent:
            node_set.add(src)
            raw_edges.append((src, tgt, r["source_id"]))

    # Resolve document info for all nodes
    known = {}
    for r in await db.fetch(
        "SELECT id, document_number, title, site_key, algo_doc_type FROM documents WHERE document_number != ''"
    ):
        if r["document_number"] in node_set:
            known[r["document_number"]] = dict(r)

    # Build node list
    nodes = []
    for ref in node_set:
        info = frequent.get(ref, {})
        resolved = known.get(ref)
        nodes.append({
            "id": ref, "label": ref,
            "level": info.get("level") or get_admin_level(ref),
            "citations": info.get("count", 0),
            "title": resolved["title"] if resolved else "",
            "resolved": bool(resolved),
            "doc_type": resolved.get("algo_doc_type", "") if resolved else "",
        })

    edges = [
        {"source": src, "target": tgt, "source_id": sid}
        for src, tgt, sid in raw_edges
        if src in node_set and tgt in node_set
    ]

    return {"nodes": nodes, "edges": edges}
