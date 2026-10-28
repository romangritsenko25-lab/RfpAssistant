"""Questionnaire jobs: upload, progress, review, reference answers and export."""

from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Query, UploadFile, status
from fastapi.responses import Response

from rfp.api.deps import Conn, EmbedderDep, RunnerDep, SettingsDep
from rfp.api.schemas import Page, ReferenceResponse, ReviewRequest
from rfp.auth import CurrentUser
from rfp.services import jobs as jobs_service
from rfp.services.errors import InvalidInputError
from rfp.services.references import save_reference_answer

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a questionnaire and start answering it",
    description=(
        "Accepts an XLSX, DOCX or PDF file. The questions are extracted at once (an unreadable file "
        "or one without questions is rejected with 422); answering runs in the background. Poll "
        "`GET /api/jobs/{job_id}/status` for progress. For XLSX the question and answer columns are "
        "detected from the header row unless given."
    ),
)
def create_job(
    conn: Conn,
    runner: RunnerDep,
    settings: SettingsDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="XLSX, DOCX or PDF questionnaire")],
    sheet: Annotated[str | None, Form(description="XLSX sheet name; the first sheet if omitted")] = None,
    question_col: Annotated[
        str | None, Form(description="XLSX column with the questions; detected from the headers if omitted")
    ] = None,
    answer_col: Annotated[
        str | None,
        Form(description="XLSX column the answers go to; detected if omitted; must differ from question_col"),
    ] = None,
    header_row: Annotated[
        int | None, Form(ge=0, description="XLSX header row; detected if omitted (questions start below it)")
    ] = None,
    number_col: Annotated[str | None, Form(description="XLSX column with item numbers (optional)")] = None,
) -> jobs_service.JobSummary:
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise InvalidInputError(f"The file is larger than {settings.max_upload_mb} MB.")
    params = jobs_service.JobParams(
        sheet=sheet or None,
        question_col=question_col,
        answer_col=answer_col,
        header_row=header_row,
        number_col=number_col,
    )
    job = jobs_service.create_job(conn, user.username, file.filename or "upload", data, params)
    runner.submit(job.id)
    return job


@router.get("", summary="List jobs, newest first")
def list_jobs(
    conn: Conn,
    _: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[jobs_service.JobSummary]:
    items, total = jobs_service.list_jobs(conn, limit, offset)
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{job_id}", summary="A job with all questions, answers, statuses and citations")
def get_job(job_id: int, conn: Conn, _: CurrentUser) -> jobs_service.JobDetail:
    return jobs_service.get_job(conn, job_id)


@router.get("/{job_id}/status", summary="Job status and progress only (cheap to poll)")
def get_job_status(job_id: int, conn: Conn, _: CurrentUser) -> jobs_service.JobSummary:
    return jobs_service.get_job_summary(conn, job_id)


@router.patch(
    "/{job_id}/answers/{qid}",
    summary="Edit an answer or change its review status",
    description="Records who changed the answer and when. The model's original draft stays in `model_text`.",
)
def review_answer(
    job_id: int, qid: str, body: ReviewRequest, conn: Conn, user: CurrentUser
) -> jobs_service.JobItem:
    return jobs_service.review_item(conn, job_id, qid, user.username, body.text, body.status, body.note)


@router.post(
    "/{job_id}/answers/{qid}/reference",
    status_code=status.HTTP_201_CREATED,
    summary="Save a reviewed answer to the knowledge base as a reference answer",
    description=(
        "Only `approved` or `edited` answers qualify. Later questions find it through the normal search."
    ),
)
def save_reference(
    job_id: int, qid: str, conn: Conn, embedder: EmbedderDep, user: CurrentUser
) -> ReferenceResponse:
    return ReferenceResponse(doc_id=save_reference_answer(conn, embedder, job_id, qid, user.username))


@router.get(
    "/{job_id}/export",
    summary="Download the file with the current (reviewed) answers",
    description=(
        "XLSX: answers go to the chosen column of the original file. DOCX: answers under each question. "
        "PDF: a DOCX report. Not available while the job is still running."
    ),
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def export_job(job_id: int, conn: Conn, user: CurrentUser) -> Response:
    exported = jobs_service.export_job(conn, job_id, user.username)
    disposition = "attachment; filename*=UTF-8''" + quote(exported.filename)
    return Response(
        exported.content, media_type=exported.media_type, headers={"Content-Disposition": disposition}
    )
