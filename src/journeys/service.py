"""Journeys and their segments: reads and writes."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.journeys.models import Journey, Segment

# --- Journeys ----------------------------------------------------------------


async def get_journey(db: AsyncSession, journey_id: int, company_id: int) -> Journey | None:
    journey = await db.get(Journey, journey_id)
    return journey if journey and journey.company_id == company_id else None


async def list_journeys(db: AsyncSession, company_id: int) -> list[Journey]:
    result = await db.scalars(
        select(Journey).where(Journey.company_id == company_id).order_by(Journey.created_at.desc())
    )
    return list(result)


async def create_journey(
    db: AsyncSession, company_id: int, title: str, description: str | None
) -> Journey:
    journey = Journey(company_id=company_id, title=title, description=description)
    db.add(journey)
    await db.commit()
    await db.refresh(journey)
    return journey


async def update_journey(db: AsyncSession, journey: Journey, changes: dict[str, Any]) -> Journey:
    for field, value in changes.items():
        setattr(journey, field, value)
    await db.commit()
    await db.refresh(journey)
    return journey


async def delete_journey(db: AsyncSession, journey: Journey) -> None:
    """Segments, documents and their data go with it (ON DELETE CASCADE)."""
    await db.delete(journey)
    await db.commit()


async def count_journeys(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Journey)) or 0


async def count_by_company(db: AsyncSession) -> dict[int, int]:
    """{company_id: number of journeys}; companies without journeys are missing."""
    result = await db.execute(select(Journey.company_id, func.count()).group_by(Journey.company_id))
    return dict(result.all())


# --- Segments ----------------------------------------------------------------


async def get_segment(db: AsyncSession, segment_id: int, company_id: int) -> Segment | None:
    """A segment, only if its journey belongs to `company_id`."""
    return await db.scalar(
        select(Segment)
        .join(Journey, Journey.id == Segment.journey_id)
        .where(Segment.id == segment_id, Journey.company_id == company_id)
    )


async def list_segments(db: AsyncSession, journey_id: int) -> list[Segment]:
    result = await db.scalars(
        select(Segment)
        .where(Segment.journey_id == journey_id)
        .order_by(Segment.position, Segment.id)
    )
    return list(result)


async def count_segments(db: AsyncSession, journey_ids: list[int]) -> dict[int, int]:
    """{journey_id: number of segments}."""
    if not journey_ids:
        return {}
    result = await db.execute(
        select(Segment.journey_id, func.count())
        .where(Segment.journey_id.in_(journey_ids))
        .group_by(Segment.journey_id)
    )
    return dict(result.all())


async def _ensure_segment_name_free(
    db: AsyncSession, journey_id: int, name: str, except_id: int | None = None
) -> None:
    """Segment names are unique within a journey, ignoring case."""
    existing = await db.scalar(
        select(Segment).where(
            Segment.journey_id == journey_id, func.lower(Segment.name) == name.strip().lower()
        )
    )
    if existing and existing.id != except_id:
        message = f"“{name}” already exists in this journey"
        details = (
            None
            if except_id
            else AppError.field("name", "Segment names must be unique within a journey")
        )
        raise AppError.conflict(message, details)


async def create_segment(db: AsyncSession, journey_id: int, name: str) -> Segment:
    await _ensure_segment_name_free(db, journey_id, name)
    last = await db.scalar(
        select(func.max(Segment.position)).where(Segment.journey_id == journey_id)
    )
    segment = Segment(journey_id=journey_id, name=name, position=0 if last is None else last + 1)
    db.add(segment)
    await db.commit()
    return segment


async def rename_segment(db: AsyncSession, segment: Segment, name: str) -> Segment:
    await _ensure_segment_name_free(db, segment.journey_id, name, except_id=segment.id)
    segment.name = name
    await db.commit()
    return segment


async def delete_segment(db: AsyncSession, segment: Segment) -> None:
    """Its documents go with it (ON DELETE CASCADE); files on disk are removed by the caller."""
    await db.delete(segment)
    await db.commit()
