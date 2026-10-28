"""Questionnaire pages: the job list, upload, the review table and in-place editing via HTMX."""

from collections import Counter
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import Response

from rfp.api.deps import Conn, EmbedderDep, RunnerDep, SettingsDep
from rfp.services import jobs as jobs_service
from rfp.services.errors import ConflictError, InvalidInputError, NotFoundError, ServiceError
from rfp.services.jobs import JobItem
from rfp.services.references import save_reference_answer
from rfp.web.common import WebUser, redirect, render, ru

router = APIRouter(include_in_schema=False)

PAGE_SIZE = 25
READY = frozenset({"answered", "approved", "edited"})
FILTERS: dict[str, frozenset[str] | None] = {
    "all": None,
    "ready": READY,
    "review": frozenset({"needs_review"}),
    "no_data": frozenset({"no_data"}),
}
ERROR_STATUS = {NotFoundError: 404, ConflictError: 409, InvalidInputError: 422}


def error_page(request: Request, user, exc: ServiceError) -> Response:
    code = next((c for kind, c in ERROR_STATUS.items() if isinstance(exc, kind)), 400)
    return render(
        request,
        "error.html",
        user,
        status_code=code,
        title="Не удалось выполнить действие",
        message=ru(str(exc)),
    )


def tally(items: list[JobItem]) -> dict[str, int]:
    """Counters shown in the summary tiles."""
    counts = Counter(item.status for item in items)
    return {
        "all": len(items),
        "ready": sum(counts[s] for s in READY),
        "review": counts["needs_review"],
        "no_data": counts["no_data"],
        "pending": counts["pending"],
    }


def current_filter(value: str) -> str:
    return value if value in FILTERS else "all"


def status_counts(conn, job_ids: list[int]) -> dict[int, dict[str, int]]:
    """Per job: how many questions are ready / need review / have no data (one query for the whole page)."""
    result: dict[int, dict[str, int]] = {
        job_id: {"ready": 0, "review": 0, "no_data": 0} for job_id in job_ids
    }
    if not job_ids:
        return result
    rows = conn.execute(
        "SELECT job_id, status, count(*) FROM job_items WHERE job_id = ANY(%s) GROUP BY job_id, status",
        (job_ids,),
    ).fetchall()
    group = {**dict.fromkeys(READY, "ready"), "needs_review": "review", "no_data": "no_data"}
    for job_id, status, count in rows:
        if status in group:
            result[job_id][group[status]] += count
    return result


# --- job list -----------------------------------------------------------------------------------


def _list_context(conn, page: int) -> dict:
    jobs, total = jobs_service.list_jobs(conn, PAGE_SIZE, (page - 1) * PAGE_SIZE)
    return {
        "jobs": jobs,
        "counts": status_counts(conn, [job.id for job in jobs]),
        "active_jobs": any(job.status in ("queued", "running") for job in jobs),
        "page": page,
        "total": total,
        "first": (page - 1) * PAGE_SIZE + 1 if jobs else 0,
        "last": (page - 1) * PAGE_SIZE + len(jobs),
        "prev_url": f"/jobs?page={page - 1}" if page > 1 else None,
        "next_url": f"/jobs?page={page + 1}" if page * PAGE_SIZE < total else None,
    }


@router.get("/jobs")
def jobs_page(request: Request, conn: Conn, user: WebUser, page: Annotated[int, Query(ge=1)] = 1) -> Response:
    return render(request, "jobs.html", user, active="jobs", form_error=None, **_list_context(conn, page))


@router.get("/jobs/table")
def jobs_table(
    request: Request, conn: Conn, user: WebUser, page: Annotated[int, Query(ge=1)] = 1
) -> Response:
    """The job table alone; polled while any job is still running."""
    return render(request, "_jobs_table.html", user, **_list_context(conn, page))


def _header_row(value: str | None) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    if not value.isdigit():
        raise InvalidInputError("The header row must be a non-negative number.")
    return int(value)


@router.post("/jobs")
def upload_job(
    request: Request,
    conn: Conn,
    runner: RunnerDep,
    settings: SettingsDep,
    user: WebUser,
    file: Annotated[UploadFile, File()],
    sheet: Annotated[str | None, Form()] = None,
    question_col: Annotated[str | None, Form()] = None,
    answer_col: Annotated[str | None, Form()] = None,
    header_row: Annotated[str | None, Form()] = None,
    number_col: Annotated[str | None, Form()] = None,
) -> Response:
    try:
        limit = settings.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise InvalidInputError(f"The file is larger than {settings.max_upload_mb} MB.")
        params = jobs_service.JobParams(
            sheet=(sheet or "").strip() or None,
            question_col=(question_col or "").strip() or None,
            answer_col=(answer_col or "").strip() or None,
            header_row=_header_row(header_row),
            number_col=(number_col or "").strip() or None,
        )
        job = jobs_service.create_job(conn, user.username, file.filename or "upload", data, params)
    except ServiceError as exc:
        return render(
            request,
            "jobs.html",
            user,
            status_code=422,
            active="jobs",
            form_error=ru(str(exc)),
            **_list_context(conn, 1),
        )
    runner.submit(job.id)
    return redirect(f"/jobs/{job.id}")


# --- one job ------------------------------------------------------------------------------------


@router.get("/jobs/{job_id}")
def job_page(request: Request, job_id: int, conn: Conn, user: WebUser, f: str = "all") -> Response:
    try:
        job = jobs_service.get_job(conn, job_id)
    except NotFoundError as exc:
        return error_page(request, user, exc)
    f = current_filter(f)
    wanted = FILTERS[f]
    items = [item for item in job.items if wanted is None or item.status in wanted]
    return render(
        request,
        "job.html",
        user,
        active="jobs",
        job=job,
        items=items,
        counts=tally(job.items),
        f=f,
    )


@router.get("/jobs/{job_id}/progress")
def job_progress(request: Request, job_id: int, conn: Conn, user: WebUser) -> Response:
    """Progress bar fragment, polled every 2 s; when the job ends the browser reloads the page."""
    try:
        job = jobs_service.get_job_summary(conn, job_id)
    except NotFoundError:
        return Response(status_code=404)
    response = render(request, "_progress.html", user, job=job)
    if job.status in ("done", "failed"):
        response.headers["HX-Refresh"] = "true"
    return response


@router.get("/jobs/{job_id}/summary")
def job_summary(request: Request, job_id: int, conn: Conn, user: WebUser, f: str = "all") -> Response:
    try:
        job = jobs_service.get_job(conn, job_id)
    except NotFoundError:
        return Response(status_code=404)
    return render(request, "_summary.html", user, job=job, counts=tally(job.items), f=current_filter(f))


@router.get("/jobs/{job_id}/export")
def export_job(request: Request, job_id: int, conn: Conn, user: WebUser) -> Response:
    try:
        exported = jobs_service.export_job(conn, job_id, user.username)
    except ServiceError as exc:
        return error_page(request, user, exc)
    disposition = "attachment; filename*=UTF-8''" + quote(exported.filename)
    return Response(
        exported.content, media_type=exported.media_type, headers={"Content-Disposition": disposition}
    )


# --- single answer (HTMX fragments: each returns the row group of one question) -------------------


def _find_item(conn, job_id: int, qid: str) -> JobItem:
    for item in jobs_service.get_job(conn, job_id).items:
        if item.qid == qid:
            return item
    raise NotFoundError(f"Question {qid} not found in job {job_id}.")


def _row(
    request: Request, user, job_id: int, item: JobItem, f: str, *, changed: bool = False, **flags
) -> Response:
    response = render(request, "_item.html", user, job_id=job_id, item=item, f=current_filter(f), **flags)
    if changed:
        response.headers["HX-Trigger"] = "item-changed"
    return response


@router.get("/jobs/{job_id}/items/{qid}")
def item_row(request: Request, job_id: int, qid: str, conn: Conn, user: WebUser, f: str = "all") -> Response:
    try:
        item = _find_item(conn, job_id, qid)
    except NotFoundError:
        return Response(status_code=404)
    return _row(request, user, job_id, item, f, expanded=True)


@router.get("/jobs/{job_id}/items/{qid}/edit")
def item_edit_form(
    request: Request, job_id: int, qid: str, conn: Conn, user: WebUser, f: str = "all"
) -> Response:
    try:
        item = _find_item(conn, job_id, qid)
    except NotFoundError:
        return Response(status_code=404)
    return _row(request, user, job_id, item, f, expanded=True, editing=True, draft=item.text)


@router.post("/jobs/{job_id}/items/{qid}/edit")
def item_save(
    request: Request,
    job_id: int,
    qid: str,
    conn: Conn,
    user: WebUser,
    text: Annotated[str, Form()],
    f: str = "all",
) -> Response:
    try:
        item = jobs_service.review_item(conn, job_id, qid, user.username, text=text)
    except NotFoundError:
        return Response(status_code=404)
    except ServiceError as exc:
        item = _find_item(conn, job_id, qid)
        return _row(
            request, user, job_id, item, f, expanded=True, editing=True, draft=text, error=ru(str(exc))
        )
    return _row(request, user, job_id, item, f, changed=True, expanded=True, flash="Ответ сохранён.")


@router.post("/jobs/{job_id}/items/{qid}/approve")
def item_approve(
    request: Request, job_id: int, qid: str, conn: Conn, user: WebUser, f: str = "all"
) -> Response:
    try:
        item = jobs_service.review_item(conn, job_id, qid, user.username, status="approved")
    except NotFoundError:
        return Response(status_code=404)
    except ServiceError as exc:
        return _row(
            request, user, job_id, _find_item(conn, job_id, qid), f, expanded=True, error=ru(str(exc))
        )
    return _row(request, user, job_id, item, f, changed=True)


@router.post("/jobs/{job_id}/items/{qid}/reference")
def item_reference(
    request: Request,
    job_id: int,
    qid: str,
    conn: Conn,
    embedder: EmbedderDep,
    user: WebUser,
    f: str = "all",
) -> Response:
    try:
        doc_id = save_reference_answer(conn, embedder, job_id, qid, user.username)
        item = _find_item(conn, job_id, qid)
    except NotFoundError:
        return Response(status_code=404)
    except ServiceError as exc:
        return _row(
            request, user, job_id, _find_item(conn, job_id, qid), f, expanded=True, error=ru(str(exc))
        )
    return _row(
        request, user, job_id, item, f, expanded=True, flash=f"Сохранено в базе знаний как эталон {doc_id}."
    )
