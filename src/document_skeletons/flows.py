"""Skeleton use cases that need another module's data."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.document_skeletons import service as skeletons
from src.document_skeletons.schemas import SkeletonListItem, SkeletonRead
from src.documents import service as documents


async def list_skeletons(db: AsyncSession, company_id: int) -> list[SkeletonListItem]:
    """Every skeleton with its field count, rule count and the journeys using it."""
    rows = await skeletons.list_skeletons(db, company_id)
    ids = [t.id for t in rows]
    field_counts, rule_counts = await skeletons.count_fields_and_rules(db, ids)
    journey_counts = await documents.journey_count_by_skeleton(db, ids)
    return [
        SkeletonListItem(
            **SkeletonRead.model_validate(t).model_dump(),
            field_count=field_counts.get(t.id, 0),
            rule_count=rule_counts.get(t.id, 0),
            journey_count=journey_counts.get(t.id, 0),
        )
        for t in rows
    ]
