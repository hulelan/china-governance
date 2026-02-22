"""Server-rendered HTML page routes."""
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from web.services.documents import (
    get_documents, get_document, get_document_citations,
    get_sites, get_stats, get_categories, search_documents,
    REF_PATTERN, get_admin_level,
)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    db = request.app.state.db
    stats = await get_stats(db)
    sites = await get_sites(db)
    categories = await get_categories(db)
    return templates.TemplateResponse("index.html", {
        "request": request, "stats": stats, "sites": sites, "categories": categories,
    })


@router.get("/browse", response_class=HTMLResponse)
async def browse(
    request: Request,
    site: str = "", category: str = "", year: str = "",
    has_docnum: str = "", page: int = 1,
):
    db = request.app.state.db
    documents, total = await get_documents(
        db, site_key=site or None, category=category or None,
        year=year or None, has_docnum=bool(has_docnum), page=page,
    )
    sites = await get_sites(db)
    categories = await get_categories(db)

    # Build pagination query string (without page)
    filters = {"site": site, "category": category, "year": year, "has_docnum": has_docnum}
    pagination_qs = urlencode({k: v for k, v in filters.items() if v})

    return templates.TemplateResponse("browse.html", {
        "request": request, "documents": documents, "total": total,
        "page": page, "sites": sites, "categories": categories,
        "filters": filters, "pagination_qs": pagination_qs,
        "stats": await get_stats(db),
    })


@router.get("/document/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int):
    db = request.app.state.db
    doc = await get_document(db, doc_id)
    if not doc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    cites, cited_by = await get_document_citations(db, doc_id)
    return templates.TemplateResponse("document.html", {
        "request": request, "doc": doc, "cites": cites, "cited_by": cited_by,
        "stats": await get_stats(db),
    })


@router.get("/compare/{doc_id}", response_class=HTMLResponse)
async def compare(request: Request, doc_id: int):
    db = request.app.state.db
    doc = await get_document(db, doc_id)
    if not doc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    return templates.TemplateResponse("compare.html", {
        "request": request, "doc": doc, "stats": await get_stats(db),
    })


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", page: int = 1):
    db = request.app.state.db
    results, total = [], 0
    if q:
        try:
            results, total = await search_documents(db, q, page)
        except Exception:
            results, total = [], 0
    return templates.TemplateResponse("search.html", {
        "request": request, "q": q, "results": results, "total": total,
        "page": page, "stats": await get_stats(db),
    })


@router.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    db = request.app.state.db
    sites = await get_sites(db)
    return templates.TemplateResponse("network.html", {
        "request": request, "sites": sites, "stats": await get_stats(db),
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    db = request.app.state.db
    stats = await get_stats(db)
    sites = await get_sites(db)

    # Timeline data
    timeline_labels = [str(yr["year"]) for yr in stats["by_year"]]
    timeline_data = [yr["count"] for yr in stats["by_year"]]

    # Citation hierarchy — compute from body text
    rows = await db.execute_fetchall(
        "SELECT body_text_cn FROM documents WHERE body_text_cn != ''"
    )
    level_counts = Counter()
    all_refs_counter = Counter()
    for row in rows:
        refs = REF_PATTERN.findall(row["body_text_cn"])
        for ref in refs:
            level_counts[get_admin_level(ref)] += 1
            all_refs_counter[ref] += 1

    hierarchy_labels = ["Central", "Provincial", "Municipal", "District", "Unknown"]
    hierarchy_data = [
        level_counts.get("central", 0), level_counts.get("provincial", 0),
        level_counts.get("municipal", 0), level_counts.get("district", 0),
        level_counts.get("unknown", 0),
    ]

    # Top cited
    known_docs = {}
    for r in await db.execute_fetchall(
        "SELECT id, document_number, title FROM documents WHERE document_number != ''"
    ):
        known_docs[r["document_number"]] = (r["id"], r["title"])

    top_cited = []
    for docnum, count in all_refs_counter.most_common(25):
        resolved = known_docs.get(docnum)
        top_cited.append({
            "docnum": docnum, "count": count, "level": get_admin_level(docnum),
            "resolved": bool(resolved),
            "resolved_id": resolved[0] if resolved else None,
            "title": resolved[1] if resolved else "",
        })

    # Coverage data
    coverage_labels = [s["name"][:20] for s in sites[:12]]
    coverage_body = [s["body_count"] for s in sites[:12]]
    coverage_no_body = [s["doc_count"] - s["body_count"] for s in sites[:12]]

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "stats": stats, "sites": sites,
        "timeline_labels": timeline_labels, "timeline_data": timeline_data,
        "hierarchy_labels": hierarchy_labels, "hierarchy_data": hierarchy_data,
        "top_cited": top_cited,
        "coverage_labels": coverage_labels, "coverage_body": coverage_body,
        "coverage_no_body": coverage_no_body,
    })
