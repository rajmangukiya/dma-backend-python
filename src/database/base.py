import os
import time
from datetime import datetime
from enum import Enum
from uuid import UUID

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


def new_id() -> UUID:
    """A UUIDv7 (RFC 9562): 48-bit millisecond timestamp + 74 random bits.

    Unlike random v4 ids, v7 ids sort in creation order, which keeps "ORDER BY id"
    meaningful and Postgres indexes compact. (Python 3.14 adds uuid.uuid7().)
    """
    milliseconds = time.time_ns() // 1_000_000
    rand = int.from_bytes(os.urandom(10))  # 80 random bits, 74 are used
    value = (
        (milliseconds & (2**48 - 1)) << 80  # unix_ts_ms
        | 0x7 << 76  # version 7
        | (rand >> 62 & 0xFFF) << 64  # rand_a (12 bits)
        | 0b10 << 62  # variant (RFC 9562)
        | rand & (2**62 - 1)  # rand_b (62 bits)
    )
    return UUID(int=value)


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
