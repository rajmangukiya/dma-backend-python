from datetime import datetime
from typing import Annotated, ClassVar
from uuid import UUID

from src.common.schemas import CamelModel, PatchRequest, trimmed
from src.document_skeletons.enums import FieldType

Title = Annotated[str, trimmed(200, required="Title is required")]
DocumentType = Annotated[str, trimmed(100, required="Document type is required")]
Description = Annotated[str, trimmed(5000)]
FieldName = Annotated[str, trimmed(150, required="Field name is required")]


# --- Requests ----------------------------------------------------------------


class CreateSkeletonRequest(CamelModel):
    title: Title
    document_type: DocumentType
    description: Description | None = None


class UpdateSkeletonRequest(PatchRequest):
    nullable: ClassVar[frozenset[str]] = frozenset({"description"})

    title: Title | None = None
    document_type: DocumentType | None = None
    description: Description | None = None


class CreateFieldRequest(CamelModel):
    name: FieldName
    type: FieldType


class UpdateFieldRequest(PatchRequest):
    name: FieldName | None = None
    type: FieldType | None = None


class AddMatchRequest(CamelModel):
    match_field_id: UUID


# --- Responses ---------------------------------------------------------------


class SkeletonRead(CamelModel):
    id: UUID
    company_id: UUID
    title: str
    document_type: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class SkeletonListItem(SkeletonRead):
    field_count: int
    rule_count: int
    journey_count: int


class FieldMatch(CamelModel):
    """A match rule, seen from the field that owns it."""

    field_id: UUID
    field_name: str
    document_skeleton_id: UUID
    document_skeleton_title: str


class SkeletonFieldDetail(CamelModel):
    id: UUID
    document_skeleton_id: UUID
    name: str
    type: FieldType
    position: int
    matches: list[FieldMatch]
    incoming_count: int  # fields on other skeletons that match this one


class SkeletonDetail(SkeletonRead):
    fields: list[SkeletonFieldDetail]


class CandidateField(CamelModel):
    id: UUID
    name: str
    type: FieldType


class MatchCandidate(CamelModel):
    """Another skeleton and its fields, offered in the "matches with" picker."""

    id: UUID
    title: str
    document_type: str
    fields: list[CandidateField]
