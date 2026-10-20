"""Document use cases: the detail view, uploads and values entered by hand."""

from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.config import get_settings
from src.common.errors import AppError
from src.documents import service as documents
from src.documents.enums import DocumentStatus
from src.documents.extraction import extraction_runner
from src.documents.matching import JourneyMatcher
from src.documents.models import Document, UploadedFile
from src.documents.schemas import (
    DocumentCounts,
    DocumentDetail,
    FieldRowRead,
    JourneyRef,
    MatchCheckRead,
    Ref,
    UploadedFileRead,
)
from src.integrations.storage import document_folder, get_storage
from src.journeys import service as journeys
from src.journeys.models import Journey

ALLOWED_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".docx", ".doc", ".csv", ".jpg", ".jpeg", ".png"}
MAX_FILES_PER_REQUEST = 20


async def document_detail(db: AsyncSession, document: Document, journey: Journey) -> DocumentDetail:
    segments = await journeys.list_segments(db, journey.id)
    graph = await documents.load_journey_graph(db, journey.id)
    current = next((d for d in graph.documents if d.id == document.id), document)
    matcher = JourneyMatcher(graph)
    files = [f for f in graph.files if f.document_id == document.id]
    file_name = {f.id: f.original_name for f in files}
    segment_name = {s.id: s.name for s in segments}
    counts = matcher.counts(current)

    return DocumentDetail(
        id=current.id,
        title=current.title,
        document_type=current.document_type,
        status=current.status,
        document_skeleton_id=current.document_skeleton_id,
        journey=JourneyRef(id=journey.id, title=journey.title),
        segment=Ref(id=current.segment_id, name=segment_name.get(current.segment_id, "")),
        files=[UploadedFileRead.model_validate(f) for f in files],
        counts=DocumentCounts.model_validate(counts) if counts else None,
        fields=[
            FieldRowRead(
                **{k: v for k, v in vars(row).items() if k != "checks"},
                source_file_name=file_name.get(row.source_file_id) if row.source_file_id else None,
                checks=[
                    MatchCheckRead(
                        **vars(check),
                        target_segment_name=segment_name.get(check.target_segment_id)
                        if check.target_segment_id
                        else None,
                    )
                    for check in row.checks
                ],
            )
            for row in matcher.rows(current)
        ],
    )


async def upload_files(
    db: AsyncSession, document: Document, journey: Journey, uploads: list[UploadFile], user_id: int
) -> int:
    """Stores the files, then re-runs extraction over all of the document's files."""
    if not uploads:
        raise AppError.bad_request("Select at least one file to upload")
    if len(uploads) > MAX_FILES_PER_REQUEST:
        raise AppError.bad_request("Too many files in one upload")

    max_mb = get_settings().max_upload_size_mb
    contents = []
    for upload in uploads:
        name = upload.filename or "file"
        if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
            raise AppError.bad_request(f"Unsupported file type: {name}")
        content = await upload.read()
        if len(content) > max_mb * 1024 * 1024:
            raise AppError.bad_request(f"Each file must be {max_mb} MB or smaller")
        contents.append((upload, name, content))

    # Everything is validated before anything is written
    storage = get_storage()
    folder = document_folder(journey.company_id, journey.id, document.id)
    await documents.add_files(
        db,
        [
            UploadedFile(
                document_id=document.id,
                original_name=name,
                storage_key=storage.save(folder, name, content),
                mime_type=upload.content_type or "application/octet-stream",
                size_bytes=len(content),
                uploaded_by_id=user_id,
            )
            for upload, name, content in contents
        ],
    )
    await extraction_runner.queue(db, document.id)
    return len(contents)


async def remove_file(db: AsyncSession, document: Document, file: UploadedFile) -> None:
    await documents.delete_file(db, file)
    get_storage().remove(file.storage_key)
    await extraction_runner.queue(db, document.id)


async def delete_document(db: AsyncSession, document: Document, journey: Journey) -> None:
    await documents.delete_document(db, document)
    get_storage().remove_folder(document_folder(journey.company_id, journey.id, document.id))


async def set_value(db: AsyncSession, document: Document, field_id: int, value: str | None) -> None:
    """Sets a value by hand; clearing it restores the extracted value."""
    if document.status != DocumentStatus.READY:
        raise AppError.bad_request("Values can be edited once extraction has finished")
    field = await documents.get_field(db, document.id, field_id)
    if not field:
        raise AppError.not_found("Field not found")
    if value:
        await documents.set_manual_value(db, field, value)
    else:
        await documents.clear_manual_value(db, field)
        await extraction_runner.queue(db, document.id)
