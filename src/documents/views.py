from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from src.auth.dependencies import CurrentCompanyId, CurrentUser, require
from src.auth.permissions import Permission
from src.common.errors import AppError
from src.common.schemas import ApiResponse, ok
from src.database.session import DbSession
from src.documents import flows, service
from src.documents.models import Document, UploadedFile
from src.documents.schemas import DocumentDetail, SetValueRequest
from src.integrations.storage import get_storage
from src.journeys import flows as journey_flows
from src.journeys import service as journeys
from src.journeys.models import Journey
from src.journeys.schemas import JourneyDetail

router = APIRouter(prefix="/documents", tags=["documents"])

can_view = [Depends(require(Permission.VIEW_JOURNEYS))]
can_manage = [Depends(require(Permission.MANAGE_JOURNEYS))]
can_edit_data = [Depends(require(Permission.MANAGE_DOCUMENT_DATA))]


async def _load(db: DbSession, company_id: int, document_id: int) -> tuple[Document, Journey]:
    """The document and its journey; 404 unless the journey belongs to the company."""
    document = await service.get_document(db, document_id)
    journey = document and await journeys.get_journey(db, document.journey_id, company_id)
    if not document or not journey:
        raise AppError.not_found("Document not found")
    return document, journey


async def _load_file(db: DbSession, document: Document, file_id: int) -> UploadedFile:
    file = await service.get_file(db, document.id, file_id)
    if not file:
        raise AppError.not_found("File not found")
    return file


@router.get("/{document_id}", dependencies=can_view)
async def get_document(
    document_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[DocumentDetail]:
    document, journey = await _load(db, company_id, document_id)
    return ok(await flows.document_detail(db, document, journey))


@router.delete("/{document_id}", dependencies=can_manage)
async def delete_document(
    document_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[JourneyDetail]:
    document, journey = await _load(db, company_id, document_id)
    await flows.delete_document(db, document, journey)
    return ok(await journey_flows.journey_detail(db, journey), "Document removed")


# multipart/form-data with one or more parts named "files"
@router.post(
    "/{document_id}/files", dependencies=can_edit_data, status_code=status.HTTP_201_CREATED
)
async def upload_files(
    document_id: int,
    db: DbSession,
    company_id: CurrentCompanyId,
    user: CurrentUser,
    files: Annotated[list[UploadFile] | None, File()] = None,
) -> ApiResponse[DocumentDetail]:
    document, journey = await _load(db, company_id, document_id)
    count = await flows.upload_files(db, document, journey, files or [], user.id)
    message = f"{count} file{'s' if count > 1 else ''} uploaded"
    return ok(await flows.document_detail(db, document, journey), message)


@router.get("/{document_id}/files/{file_id}/download", dependencies=can_view)
async def download_file(
    document_id: int, file_id: int, db: DbSession, company_id: CurrentCompanyId
) -> FileResponse:
    document, _ = await _load(db, company_id, document_id)
    file = await _load_file(db, document, file_id)
    path = get_storage().path_of(file.storage_key)
    if not path:
        raise AppError.not_found("File is missing from storage")
    # filename= sets Content-Disposition (RFC 6266, so non-ASCII names survive)
    return FileResponse(path, media_type=file.mime_type, filename=file.original_name)


@router.delete("/{document_id}/files/{file_id}", dependencies=can_edit_data)
async def delete_file(
    document_id: int, file_id: int, db: DbSession, company_id: CurrentCompanyId
) -> ApiResponse[DocumentDetail]:
    document, journey = await _load(db, company_id, document_id)
    file = await _load_file(db, document, file_id)
    await flows.remove_file(db, document, file)
    return ok(await flows.document_detail(db, document, journey), "File removed")


@router.put("/{document_id}/fields/{field_id}/value", dependencies=can_edit_data)
async def set_field_value(
    document_id: int,
    field_id: int,
    body: SetValueRequest,
    db: DbSession,
    company_id: CurrentCompanyId,
) -> ApiResponse[DocumentDetail]:
    document, journey = await _load(db, company_id, document_id)
    await flows.set_value(db, document, field_id, body.value)
    return ok(await flows.document_detail(db, document, journey), "Value saved")
