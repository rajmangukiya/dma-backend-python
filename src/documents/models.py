from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, CreatedAtMixin, TimestampMixin, pg_enum
from src.document_skeletons.enums import FieldType
from src.documents.enums import DocumentStatus


class Document(TimestampMixin, Base):
    """A skeleton placed in a journey segment.

    Title, type and fields are snapshotted at creation, so later skeleton
    edits don't change existing documents.
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    journey_id: Mapped[int] = mapped_column(
        ForeignKey("journeys.id", ondelete="CASCADE"), index=True
    )
    segment_id: Mapped[int] = mapped_column(
        ForeignKey("segments.id", ondelete="CASCADE"), index=True
    )
    # Source skeleton; kept for match resolution, nulled if the skeleton is deleted
    document_skeleton_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_skeletons.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(server_default="0")
    status: Mapped[DocumentStatus] = mapped_column(
        pg_enum(DocumentStatus, "document_status_enum"),
        server_default=DocumentStatus.PENDING.value,
    )


class DocumentField(Base):
    """Snapshot of a skeleton field, taken when the document was added."""

    __tablename__ = "document_fields"
    __table_args__ = (UniqueConstraint("document_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    document_skeleton_field_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_skeleton_fields.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[FieldType] = mapped_column(pg_enum(FieldType, "field_type_enum"))
    position: Mapped[int] = mapped_column(server_default="0")


class DocumentFieldMatchRule(Base):
    """Snapshot of a skeleton match rule.

    The target is stored as (skeleton, field name) and resolved at read time
    against every document in the same journey created from that skeleton.
    """

    __tablename__ = "document_field_match_rules"
    __table_args__ = (
        UniqueConstraint("document_field_id", "target_document_skeleton_id", "target_field_name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    document_field_id: Mapped[int] = mapped_column(
        ForeignKey("document_fields.id", ondelete="CASCADE")
    )
    target_document_skeleton_id: Mapped[int | None] = mapped_column(
        ForeignKey("document_skeletons.id", ondelete="SET NULL"), index=True
    )
    target_document_skeleton_title: Mapped[str] = mapped_column(String(200))
    target_field_name: Mapped[str] = mapped_column(String(150))


class UploadedFile(CreatedAtMixin, Base):
    """A file uploaded for a document; a document's files are read together."""

    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    original_name: Mapped[str] = mapped_column(String(255))
    # Relative to the upload directory (an S3 key later)
    storage_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(150))
    size_bytes: Mapped[int]
    uploaded_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class DocumentFieldValue(Base):
    """A field's value: extracted from files, or entered by hand (survives re-extraction)."""

    __tablename__ = "document_field_values"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_field_id: Mapped[int] = mapped_column(
        ForeignKey("document_fields.id", ondelete="CASCADE"), unique=True
    )
    value: Mapped[str | None] = mapped_column(Text)
    source_file_id: Mapped[int | None] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="SET NULL")
    )
    confidence: Mapped[int | None] = mapped_column(SmallInteger)  # 0-100, null when manual
    is_manual: Mapped[bool] = mapped_column(server_default=false())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
