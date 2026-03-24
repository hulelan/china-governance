"""China Governance Documents — Web Application.

FastAPI app serving both server-rendered HTML pages and a JSON API for
exploring 50k+ Chinese government documents across five administrative levels.

Routes:
    /                   Homepage with corpus overview
    /inbox              Date-grouped document feed (calendar view)
    /browse             Filterable document listing (date range + facets)
    /document/{id}      Document detail with citations and mini network graph
    /search             Full-text search with date range filtering
    /network            D3.js citation network visualization
    /dashboard          Charts and corpus statistics
    /chain/{topic}      Cross-level policy chain explorer
    /analysis/ai        AI governance write-up
    /analysis/subsidies Subsidy analysis report
    /changes            Document change tracker (sync diffs)
    /api/v1/...         JSON API mirrors of the above

Run with:
    uvicorn web.app:app --port 8080
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from web.database import lifespan
from web.routers import pages, api

app = FastAPI(title="China Governance Documents", lifespan=lifespan)

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Serve raw HTML files for verification
raw_html_dir = Path(__file__).parent.parent / "raw_html"
if raw_html_dir.exists():
    app.mount("/raw_html", StaticFiles(directory=str(raw_html_dir)), name="raw_html")

app.include_router(pages.router)
app.include_router(api.router, prefix="/api/v1")
