"""FastAPI dependencies shared by routers and the HTML layer: connections and application services."""

from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request

from rfp import db
from rfp.config import Settings
from rfp.embeddings import Embedder
from rfp.llm import ChatClient
from rfp.services.jobs import JobRunner


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_embedder(request: Request) -> Embedder:
    return request.app.state.embedder


def get_llm(request: Request) -> ChatClient:
    return request.app.state.llm


def get_layout_llm(request: Request) -> ChatClient:
    return request.app.state.layout_llm


def get_runner(request: Request) -> JobRunner:
    return request.app.state.runner


def get_conn(request: Request) -> Iterator[psycopg.Connection]:
    """A connection for the duration of one request (autocommit; use ``conn.transaction()`` for atomicity)."""
    conn = db.connect(request.app.state.settings.database_url)
    try:
        yield conn
    finally:
        conn.close()


Conn = Annotated[psycopg.Connection, Depends(get_conn)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
LayoutLLMDep = Annotated[ChatClient, Depends(get_layout_llm)]
RunnerDep = Annotated[JobRunner, Depends(get_runner)]
