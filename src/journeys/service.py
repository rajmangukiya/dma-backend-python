"""Journeys: reads and writes. (Full API comes in step 4; counts are used by admin.)"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.journeys.models import Journey


async def count_journeys(db: AsyncSession) -> int:
    return await db.scalar(select(func.count()).select_from(Journey)) or 0


async def count_by_company(db: AsyncSession) -> dict[int, int]:
    """{company_id: number of journeys}; companies without journeys are missing."""
    result = await db.execute(select(Journey.company_id, func.count()).group_by(Journey.company_id))
    return dict(result.all())
