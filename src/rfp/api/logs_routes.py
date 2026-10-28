"""Read access to the action log and the model request log (administrators only)."""

from typing import Annotated

from fastapi import APIRouter, Query

from rfp import audit
from rfp.api.deps import Conn
from rfp.api.schemas import Page
from rfp.auth import AdminUser

router = APIRouter(prefix="/logs", tags=["logs"])

Limit = Annotated[int, Query(ge=1, le=500)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/actions", summary="User actions: logins, uploads, edits, exports, deletions (newest first)")
def action_log(conn: Conn, _: AdminUser, limit: Limit = 100, offset: Offset = 0) -> Page[audit.ActionEntry]:
    items, total = audit.list_actions(conn, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/model-requests",
    summary="Requests to the model: question, fragments with scores, answer, tokens, cost, time",
)
def model_request_log(
    conn: Conn,
    _: AdminUser,
    limit: Limit = 100,
    offset: Offset = 0,
    job_id: Annotated[int | None, Query(description="Only requests of this job")] = None,
) -> Page[audit.ModelRequestEntry]:
    items, total = audit.list_model_requests(conn, limit, offset, job_id)
    return Page(items=items, total=total, limit=limit, offset=offset)
