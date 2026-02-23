"""China Governance Documents — Web Application."""
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
