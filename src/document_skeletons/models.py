from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin, new_id, pg_enum
from src.document_skeletons.enums import FieldType


class DocumentSkeleton(TimestampMixin, Base):
    """A document skeleton: the shape of a document and its fields."""

    __tablename__ = "document_skeletons"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class DocumentSkeletonField(Base):
    __tablename__ = "document_skeleton_fields"
    __table_args__ = (UniqueConstraint("document_skeleton_id", "name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    document_skeleton_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_skeletons.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[FieldType] = mapped_column(pg_enum(FieldType, "field_type_enum"))
    position: Mapped[int] = mapped_column(server_default="0")


class DocumentSkeletonFieldMatch(Base):
    """One-way match rule: `field` must match `match_field` (a field on another skeleton)."""

    __tablename__ = "document_skeleton_field_matches"
    __table_args__ = (CheckConstraint("field_id <> match_field_id", name="not_self"),)

    field_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_skeleton_fields.id", ondelete="CASCADE"), primary_key=True
    )
    match_field_id: Mapped[UUID] = mapped_column(
        ForeignKey("document_skeleton_fields.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
