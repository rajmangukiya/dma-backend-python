from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, CreatedAtMixin, TimestampMixin, new_id


class Journey(TimestampMixin, Base):
    __tablename__ = "journeys"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)


class Segment(CreatedAtMixin, Base):
    __tablename__ = "segments"
    # Segment names are unique within a journey
    __table_args__ = (UniqueConstraint("journey_id", "name"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    journey_id: Mapped[UUID] = mapped_column(ForeignKey("journeys.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(150))
    position: Mapped[int] = mapped_column(server_default="0")
