"""Server-rendered web interface (Jinja2 + HTMX). Pages call the service layer directly."""

from fastapi import APIRouter
from fastapi.staticfiles import StaticFiles

from rfp.web import auth_pages, jobs_pages, knowledge_pages, logs_pages
from rfp.web.common import STATIC_DIR

web_router = APIRouter()
for module in (auth_pages, jobs_pages, knowledge_pages, logs_pages):
    web_router.include_router(module.router)

static_files = StaticFiles(directory=STATIC_DIR)

__all__ = ["static_files", "web_router"]
