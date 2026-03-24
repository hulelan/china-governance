"""Server-rendered HTML page routes.

Each handler queries the database via service functions and renders a
Jinja2 template.  All pages receive a ``stats`` dict for the nav bar counters.
"""
import json
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
    get_citation_neighborhood, date_str_to_timestamp,
    REF_PATTERN, get_admin_level,
)
from web.services.inbox import get_inbox_dates, get_documents_for_date
from web.services.subsidies import (
    get_subsidy_stats, get_subsidy_by_district, get_subsidy_by_sector,
    get_subsidy_timeline, get_top_subsidy_programs, get_top_subsidy_documents,
    get_central_subsidy_linkage,
)
from web.services.changes import (
    get_recent_changes, get_sync_runs, get_change_stats,
)
from web.services.chain import get_chain, TOPIC_KEYWORDS

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def homepage(request: Request):
    """Landing page with corpus overview, site list, and category breakdown."""
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
    date_start: str = "", date_end: str = "",
    importance: str = "",
):
    """Paginated document browser with filters for site, category, year, date range, importance, and doc-number presence."""
    db = request.app.state.db
    ds = date_str_to_timestamp(date_start) if date_start else None
    de = date_str_to_timestamp(date_end) if date_end else None
    documents, total = await get_documents(
        db, site_key=site or None, category=category or None,
        year=year or None, has_docnum=bool(has_docnum), page=page,
        date_start=ds, date_end=de, importance=importance or None,
    )
    sites = await get_sites(db)
    categories = await get_categories(db)

    filters = {
        "site": site, "category": category, "year": year,
        "has_docnum": has_docnum, "date_start": date_start, "date_end": date_end,
        "importance": importance,
    }
    pagination_qs = urlencode({k: v for k, v in filters.items() if v})

    return templates.TemplateResponse("browse.html", {
        "request": request, "documents": documents, "total": total,
        "page": page, "sites": sites, "categories": categories,
        "filters": filters, "pagination_qs": pagination_qs,
        "stats": await get_stats(db),
    })


@router.get("/document/{doc_id}", response_class=HTMLResponse)
async def document_detail(request: Request, doc_id: int):
    """Single document view with metadata, body text, and forward/reverse citations."""
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
    """Side-by-side view of parsed text vs. raw HTML for a document."""
    db = request.app.state.db
    doc = await get_document(db, doc_id)
    if not doc:
        return HTMLResponse("<h1>Not found</h1>", status_code=404)
    return templates.TemplateResponse("compare.html", {
        "request": request, "doc": doc, "stats": await get_stats(db),
    })


@router.get("/search", response_class=HTMLResponse)
async def search_page(request: Request, q: str = "", page: int = 1,
                      date_start: str = "", date_end: str = ""):
    """Full-text search page with highlighted snippets, pagination, and optional date range."""
    db = request.app.state.db
    ds = date_str_to_timestamp(date_start) if date_start else None
    de = date_str_to_timestamp(date_end) if date_end else None
    results, total = [], 0
    if q:
        try:
            results, total = await search_documents(db, q, page, date_start=ds, date_end=de)
        except Exception:
            results, total = [], 0
    return templates.TemplateResponse("search.html", {
        "request": request, "q": q, "results": results, "total": total,
        "page": page, "date_start": date_start, "date_end": date_end,
        "stats": await get_stats(db),
    })


@router.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    """Interactive D3.js force-directed citation network graph."""
    db = request.app.state.db
    sites = await get_sites(db)
    return templates.TemplateResponse("network.html", {
        "request": request, "sites": sites, "stats": await get_stats(db),
    })


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Analytics dashboard with timeline, citation hierarchy, top-cited docs, and coverage charts."""
    db = request.app.state.db
    stats = await get_stats(db)
    sites = await get_sites(db)

    # Timeline data
    timeline_labels = [str(yr["year"]) for yr in stats["by_year"]]
    timeline_data = [yr["count"] for yr in stats["by_year"]]

    # Citation hierarchy — compute from body text
    rows = await db.fetch(
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
    for r in await db.fetch(
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


@router.get("/chain/{topic}", response_class=HTMLResponse)
async def chain_page(request: Request, topic: str = "ai"):
    """Policy chain page showing cross-level citation hierarchy for a topic (e.g. AI, housing)."""
    db = request.app.state.db
    stats = await get_stats(db)
    keyword = TOPIC_KEYWORDS.get(topic, topic)
    chain = await get_chain(db, keyword, topic=topic)

    return templates.TemplateResponse("chain.html", {
        "request": request, "stats": stats, "chain": chain,
        "topic": topic, "keyword": keyword, "topics": TOPIC_KEYWORDS,
    })


@router.get("/chain", response_class=HTMLResponse)
async def chain_default(request: Request):
    """Redirect /chain to /chain/ai (default topic)."""
    return await chain_page(request, "ai")


@router.get("/analysis/ai", response_class=HTMLResponse)
async def analysis_ai(request: Request):
    """Static write-up on AI governance with live document count."""
    db = request.app.state.db
    stats = await get_stats(db)
    doc_count = await db.fetchval(
        "SELECT COUNT(*) FROM documents WHERE title LIKE '%人工智能%' OR keywords LIKE '%人工智能%' OR abstract LIKE '%人工智能%'"
    )
    return templates.TemplateResponse("writeup.html", {
        "request": request, "stats": stats, "doc_count": doc_count,
    })


@router.get("/analysis/subsidies", response_class=HTMLResponse)
async def analysis_subsidies(request: Request):
    """Subsidy analysis report with district, sector, and timeline breakdowns."""
    db = request.app.state.db
    stats = await get_stats(db)
    try:
        subsidy_stats = await get_subsidy_stats(db)
        by_district = await get_subsidy_by_district(db)
        by_sector = await get_subsidy_by_sector(db)
        timeline = await get_subsidy_timeline(db)
        top_programs = await get_top_subsidy_programs(db)
        top_docs = await get_top_subsidy_documents(db)
        central_linkage = await get_central_subsidy_linkage(db)
    except Exception:
        # subsidy_items table may not exist yet
        subsidy_stats = {"documents_with_amounts": 0, "total_items": 0, "total_amount_wan": 0, "total_amount_yi": 0}
        by_district = []
        by_sector = []
        timeline = []
        top_programs = []
        top_docs = []
        central_linkage = []

    return templates.TemplateResponse("subsidies_writeup.html", {
        "request": request, "stats": stats,
        "subsidy_stats": subsidy_stats,
        "by_district": by_district,
        "by_sector": by_sector,
        "timeline": timeline,
        "top_programs": top_programs,
        "top_docs": top_docs,
        "central_linkage": central_linkage,
    })


@router.get("/inbox", response_class=HTMLResponse)
async def inbox(request: Request, site: str = "", admin_level: str = ""):
    """Temporal inbox showing documents grouped by date — 'what's new' view."""
    db = request.app.state.db
    dates = await get_inbox_dates(db, site_key=site or None, admin_level=admin_level or None)
    sites = await get_sites(db)
    # Pre-load documents for the most recent 7 dates
    for d in dates[:7]:
        d["documents"] = [dict(r) for r in await get_documents_for_date(
            db, d["date_ts"], site_key=site or None, admin_level=admin_level or None
        )]
    return templates.TemplateResponse("inbox.html", {
        "request": request, "dates": dates, "sites": sites,
        "filters": {"site": site, "admin_level": admin_level},
        "stats": await get_stats(db),
    })


@router.get("/changes", response_class=HTMLResponse)
async def changes_page(request: Request):
    """Document change tracker showing sync-run diffs (adds, modifications, deletions)."""
    db = request.app.state.db
    stats = await get_stats(db)
    try:
        change_stats = await get_change_stats(db)
        sync_runs = await get_sync_runs(db)
        recent_changes = await get_recent_changes(db)
    except Exception:
        # document_changes table may not exist yet
        change_stats = {"total": 0, "added": 0, "modified": 0, "deleted": 0, "runs": 0}
        sync_runs = []
        recent_changes = []

    return templates.TemplateResponse("changes.html", {
        "request": request, "stats": stats,
        "change_stats": change_stats,
        "sync_runs": sync_runs,
        "recent_changes": recent_changes,
    })
