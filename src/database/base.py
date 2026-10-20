from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable constraint names (pk_users, fk_users_company_id_companies, ...)
# so Alembic can generate, rename and drop them reliably
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Every table model inherits from this; Alembic reads Base.metadata."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    """created_at + updated_at (updated by SQLAlchemy whenever the row changes)."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def pg_enum(enum_class: type[Enum], name: str) -> SAEnum:
    """A PostgreSQL enum type that stores the members' values ("admin"), not names ("ADMIN")."""
    return SAEnum(enum_class, name=name, values_callable=lambda e: [m.value for m in e])
