from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, pg_enum
from app.db.models.enums import FieldType


class DocumentTemplate(TimestampMixin, Base):
    """A document skeleton: the shape of a document and its fields."""

    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text)


class DocumentTemplateField(Base):
    __tablename__ = "document_template_fields"
    __table_args__ = (UniqueConstraint("template_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("document_templates.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(150))
    type: Mapped[FieldType] = mapped_column(pg_enum(FieldType, "field_type_enum"))
    position: Mapped[int] = mapped_column(server_default="0")


class DocumentTemplateFieldMatch(Base):
    """One-way match rule: `field` must match `match_field` (a field on another skeleton)."""

    __tablename__ = "document_template_field_matches"
    __table_args__ = (CheckConstraint("field_id <> match_field_id", name="not_self"),)

    field_id: Mapped[int] = mapped_column(
        ForeignKey("document_template_fields.id", ondelete="CASCADE"), primary_key=True
    )
    match_field_id: Mapped[int] = mapped_column(
        ForeignKey("document_template_fields.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
