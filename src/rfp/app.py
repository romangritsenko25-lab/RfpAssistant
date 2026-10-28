"""FastAPI application: database lifecycle and the health endpoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from rfp import db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = db.connect()
    try:
        db.apply_schema(conn)
        app.state.conn = conn
        yield
    finally:
        conn.close()


app = FastAPI(title="RFP Assistant", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    with app.state.conn.cursor() as cur:
        cur.execute("SELECT 1")
        cur.fetchone()
    return {"status": "ok", "db": "ok"}
