"""Log pages for administrators: user actions and requests to the model."""

import json
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from rfp import audit
from rfp.api.deps import Conn
from rfp.web.common import WebUser, render

router = APIRouter(include_in_schema=False)

PAGE_SIZE = 50


def _details(details: dict) -> str:
    return json.dumps(details, ensure_ascii=False) if details else ""


@router.get("/logs")
def logs_page(
    request: Request,
    conn: Conn,
    user: WebUser,
    tab: str = "actions",
    page: Annotated[int, Query(ge=1)] = 1,
    job_id: Annotated[int | None, Query(ge=1)] = None,
) -> Response:
    if not user.is_admin:
        return render(
            request,
            "error.html",
            user,
            status_code=403,
            title="Нет доступа",
            message="Журналы доступны только администратору.",
        )
    tab = "model" if tab == "model" else "actions"
    offset = (page - 1) * PAGE_SIZE
    if tab == "model":
        entries, total = audit.list_model_requests(conn, PAGE_SIZE, offset, job_id)
    else:
        entries, total = audit.list_actions(conn, PAGE_SIZE, offset)

    def page_url(number: int) -> str:
        query = {"tab": tab, "page": number}
        if job_id is not None and tab == "model":
            query["job_id"] = job_id
        return f"/logs?{urlencode(query)}"

    return render(
        request,
        "logs.html",
        user,
        active="logs",
        tab=tab,
        entries=entries,
        details=_details,
        job_id=job_id,
        total=total,
        first=offset + 1 if entries else 0,
        last=offset + len(entries),
        prev_url=page_url(page - 1) if page > 1 else None,
        next_url=page_url(page + 1) if offset + len(entries) < total else None,
    )
