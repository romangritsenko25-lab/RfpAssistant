"""Knowledge base pages: document table, upload, delete and re-synchronisation."""

from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import Response

from rfp.api.deps import Conn, EmbedderDep, SettingsDep
from rfp.services import knowledge
from rfp.services.errors import InvalidInputError, NotFoundError, ServiceError
from rfp.web.common import WebUser, redirect, render, ru

router = APIRouter(include_in_schema=False)


def _page(request: Request, conn, user, *, status_code: int = 200, form_error: str | None = None) -> Response:
    return render(
        request,
        "knowledge.html",
        user,
        status_code=status_code,
        active="knowledge",
        documents=knowledge.list_documents(conn),
        form_error=form_error,
    )


@router.get("/knowledge")
def knowledge_page(request: Request, conn: Conn, user: WebUser) -> Response:
    return _page(request, conn, user)


@router.post("/knowledge/upload")
def upload(
    request: Request,
    conn: Conn,
    embedder: EmbedderDep,
    settings: SettingsDep,
    user: WebUser,
    file: Annotated[UploadFile, File()],
) -> Response:
    try:
        limit = settings.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise InvalidInputError(f"The file is larger than {settings.max_upload_mb} MB.")
        outcome = knowledge.upload_document(
            conn, embedder, settings.kb_dir, user.username, file.filename or "upload", data
        )
    except ServiceError as exc:
        return _page(request, conn, user, status_code=422, form_error=ru(str(exc)))
    notice = "doc_unchanged" if outcome.status == "unchanged" else "doc_uploaded"
    return redirect("/knowledge", notice, outcome.filename)


@router.post("/knowledge/reindex")
def reindex(conn: Conn, embedder: EmbedderDep, settings: SettingsDep, user: WebUser) -> Response:
    outcomes = knowledge.reindex(conn, embedder, settings.kb_dir, user.username)
    counts = {s: sum(o.status == s for o in outcomes) for s in ("indexed", "removed", "failed")}
    summary = (
        f"добавлено или обновлено {counts['indexed']}, удалено {counts['removed']}, "
        f"с ошибкой {counts['failed']}"
    )
    return redirect("/knowledge", "reindexed", summary)


@router.post("/knowledge/{doc_id}/delete")
def delete(conn: Conn, settings: SettingsDep, user: WebUser, doc_id: str) -> Response:
    try:
        knowledge.delete_document(conn, settings.kb_dir, user.username, doc_id)
    except NotFoundError:
        return redirect("/knowledge", "doc_missing", doc_id)
    return redirect("/knowledge", "doc_deleted", doc_id)
