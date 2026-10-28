"""FastAPI application: database lifecycle, background workers, the health check and the ``/api`` routes."""

import logging
import secrets
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rfp import db
from rfp.api.router import api_router
from rfp.auth import bootstrap_admin
from rfp.config import Settings, get_settings
from rfp.embeddings import Embedder, get_embedder
from rfp.ingest import watch_folder
from rfp.llm import ChatClient, OpenAIChatClient
from rfp.services.errors import ConflictError, InvalidInputError, NotFoundError, ServiceError
from rfp.services.jobs import JobRunner
from rfp.web import static_files, web_router

log = logging.getLogger(__name__)

DESCRIPTION = """
Drafts answers to RFPs and customer questionnaires from a knowledge base. Every answer carries
citations to the fragments it is based on; when the base has no data the answer says so.

All `/api` endpoints except `POST /api/auth/login` need a session: log in first, the signed cookie
is then sent by the browser (or by any HTTP client that keeps cookies). Typical flow: upload a
questionnaire (`POST /api/jobs`), poll its status, review the answers (`PATCH`), optionally save
reviewed answers as reference answers, download the filled file (`GET .../export`).
"""

TAGS = [
    {"name": "auth", "description": "Login, logout, current user."},
    {"name": "jobs", "description": "Questionnaire processing, review of answers and export."},
    {"name": "knowledge base", "description": "Documents the answers are drawn from."},
    {"name": "logs", "description": "Action log and model request log (administrators)."},
    {"name": "system", "description": "Health check."},
]

_STATUS_BY_ERROR: dict[type[ServiceError], int] = {
    NotFoundError: 404,
    ConflictError: 409,
    InvalidInputError: 422,
}


def create_app(
    settings: Settings | None = None, *, embedder: Embedder | None = None, llm: ChatClient | None = None
) -> FastAPI:
    """Build the application; ``settings``, ``embedder`` and ``llm`` default to the configured ones."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        cfg = settings or get_settings()
        conn = db.connect(cfg.database_url)
        stop_watching = threading.Event()
        runner: JobRunner | None = None
        watcher: threading.Thread | None = None
        try:
            db.apply_schema(conn, cfg.embedding_dim)
            if cfg.secret_key is None:
                log.warning(
                    "SECRET_KEY is not set: using a random key, sessions end when the process restarts"
                )
            app.state.secret_key = (
                cfg.secret_key.get_secret_value() if cfg.secret_key else secrets.token_urlsafe(32)
            )
            app.state.settings = cfg
            app.state.conn = conn
            app.state.embedder = embedder or get_embedder(cfg)
            app.state.llm = llm or OpenAIChatClient(cfg)
            bootstrap_admin(conn, cfg)

            def connect():
                return db.connect(cfg.database_url)

            runner = JobRunner(connect, app.state.embedder, app.state.llm, cfg)
            app.state.runner = runner
            resumed = runner.resume_unfinished(conn)
            if resumed:
                log.info("Resumed %s unfinished job(s)", resumed)
            if cfg.watch_kb:
                cfg.kb_dir.mkdir(parents=True, exist_ok=True)
                watcher = threading.Thread(
                    target=watch_folder,
                    args=(connect, app.state.embedder, cfg.kb_dir, cfg.poll_interval_s, stop_watching),
                    name="kb-watcher",
                    daemon=True,
                )
                watcher.start()
            yield
        finally:
            stop_watching.set()
            if runner:
                runner.shutdown()
            if watcher:
                watcher.join(timeout=5)
            conn.close()

    app = FastAPI(title="RFP Assistant", description=DESCRIPTION, openapi_tags=TAGS, lifespan=lifespan)

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, exc: ServiceError) -> JSONResponse:
        code = next((c for kind, c in _STATUS_BY_ERROR.items() if isinstance(exc, kind)), 400)
        return JSONResponse({"detail": str(exc)}, status_code=code)

    @app.get("/health", tags=["system"], summary="Liveness and database check (no login needed)")
    def health() -> dict[str, str]:
        with app.state.conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return {"status": "ok", "db": "ok"}

    app.include_router(api_router)
    app.include_router(web_router)
    app.mount("/static", static_files, name="static")
    return app


app = create_app()
