from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from src.common.schemas import CamelModel
from src.document_skeletons.enums import FieldType
from src.documents.enums import DocumentStatus
from src.documents.matching import CheckStatus, FieldResult

# --- Requests ----------------------------------------------------------------


class SetValueRequest(CamelModel):
    """null or "" clears a value entered by hand and restores the extracted one."""

    value: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None


# --- Responses ---------------------------------------------------------------


class DocumentCounts(CamelModel):
    total: int
    extracted: int
    not_extracted: int
    matched: int
    not_matched: int


class DocumentSummary(CamelModel):
    """A document as listed inside its journey's segment."""

    id: int
    segment_id: int
    document_skeleton_id: int | None
    title: str
    document_type: str
    status: DocumentStatus
    file_count: int
    counts: DocumentCounts | None


class UploadedFileRead(CamelModel):
    """Never includes the storage key."""

    id: int
    document_id: int
    original_name: str
    mime_type: str
    size_bytes: int
    uploaded_by_id: int | None
    created_at: datetime


class MatchCheckRead(CamelModel):
    target_document_skeleton_title: str
    target_field_name: str
    target_document_id: int | None
    target_document_title: str | None
    target_segment_id: int | None
    target_segment_name: str | None
    value: str | None
    status: CheckStatus


class FieldRowRead(CamelModel):
    id: int
    name: str
    type: FieldType
    value: str | None
    is_manual: bool
    confidence: int | None
    source_file_id: int | None
    source_file_name: str | None
    result: FieldResult
    checks: list[MatchCheckRead]


class Ref(CamelModel):
    id: int
    name: str


class JourneyRef(CamelModel):
    id: int
    title: str


class DocumentDetail(CamelModel):
    id: int
    title: str
    document_type: str
    status: DocumentStatus
    document_skeleton_id: int | None
    journey: JourneyRef
    segment: Ref
    files: list[UploadedFileRead]
    counts: DocumentCounts | None
    fields: list[FieldRowRead]
