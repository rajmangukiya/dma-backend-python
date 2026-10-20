from datetime import datetime
from typing import Annotated, ClassVar, Literal

from pydantic import Field

from src.common.schemas import CamelModel, PatchRequest, trimmed
from src.documents.schemas import DocumentSummary

Title = Annotated[str, trimmed(200, required="Title is required")]
Description = Annotated[str, trimmed(5000)]
SegmentName = Annotated[str, trimmed(150, required="Segment name is required")]

# Draft until it has segments; complete once every document has files
JourneyStatus = Literal["draft", "in_progress", "complete"]


# --- Requests ----------------------------------------------------------------


class CreateJourneyRequest(CamelModel):
    title: Title
    description: Description | None = None


class UpdateJourneyRequest(PatchRequest):
    nullable: ClassVar[frozenset[str]] = frozenset({"description"})

    title: Title | None = None
    description: Description | None = None


class SegmentNameRequest(CamelModel):
    """Body of "add segment" and "rename segment"."""

    name: SegmentName


class AddDocumentRequest(CamelModel):
    document_skeleton_id: Annotated[int, Field(gt=0)]


# --- Responses ---------------------------------------------------------------


class JourneyRead(CamelModel):
    id: int
    company_id: int
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class JourneyListItem(JourneyRead):
    segment_count: int
    document_count: int
    uploaded_count: int
    status: JourneyStatus


class JourneyStats(CamelModel):
    documents: int
    uploaded: int
    matched: int
    not_matched: int


class SegmentWithDocuments(CamelModel):
    id: int
    journey_id: int
    name: str
    position: int
    created_at: datetime
    documents: list[DocumentSummary]


class JourneyDetail(JourneyRead):
    stats: JourneyStats
    segments: list[SegmentWithDocuments]
