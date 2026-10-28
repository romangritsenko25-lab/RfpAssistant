"""Knowledge base: documents, upload, deletion and re-synchronisation."""

from typing import Annotated

from fastapi import APIRouter, File, UploadFile, status

from rfp.api.deps import Conn, EmbedderDep, SettingsDep
from rfp.auth import CurrentUser
from rfp.services import knowledge
from rfp.services.errors import InvalidInputError

router = APIRouter(prefix="/documents", tags=["knowledge base"])


@router.get("", summary="Documents in the knowledge base with the date indexed and the number of chunks")
def list_documents(conn: Conn, _: CurrentUser) -> list[knowledge.DocumentInfo]:
    return knowledge.list_documents(conn)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document into the knowledge base and index it",
    description="DOCX, PDF, Markdown or XLSX. A file with the same name replaces the earlier version.",
)
def upload_document(
    conn: Conn,
    embedder: EmbedderDep,
    settings: SettingsDep,
    user: CurrentUser,
    file: Annotated[UploadFile, File(description="Document to index")],
) -> knowledge.IndexOutcome:
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise InvalidInputError(f"The file is larger than {settings.max_upload_mb} MB.")
    return knowledge.upload_document(
        conn, embedder, settings.kb_dir, user.username, file.filename or "upload", data
    )


@router.post(
    "/reindex",
    summary="Synchronise the index with the knowledge-base folder now",
    description=(
        "Indexes new and changed files and removes documents whose files are gone; "
        "unchanged files are skipped."
    ),
)
def reindex(
    conn: Conn, embedder: EmbedderDep, settings: SettingsDep, user: CurrentUser
) -> list[knowledge.IndexOutcome]:
    return knowledge.reindex(conn, embedder, settings.kb_dir, user.username)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a document (and its file) from the knowledge base",
)
def delete_document(doc_id: str, conn: Conn, settings: SettingsDep, user: CurrentUser) -> None:
    knowledge.delete_document(conn, settings.kb_dir, user.username, doc_id)
