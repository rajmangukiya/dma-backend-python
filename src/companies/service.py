"""Companies: reads and writes."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.companies.models import Company


async def get_company(db: AsyncSession, company_id: int) -> Company | None:
    return await db.get(Company, company_id)


async def get_company_by_name(db: AsyncSession, name: str) -> Company | None:
    """Case-insensitive: "Acme" and "acme" are the same company."""
    return await db.scalar(select(Company).where(func.lower(Company.name) == name.strip().lower()))


async def list_companies(db: AsyncSession) -> list[Company]:
    return list(await db.scalars(select(Company).order_by(Company.created_at.desc())))


async def count_companies(db: AsyncSession, *, active_only: bool = False) -> int:
    query = select(func.count()).select_from(Company)
    if active_only:
        query = query.where(Company.is_active)
    return await db.scalar(query) or 0


async def is_company_active(db: AsyncSession, company_id: int | None) -> bool:
    """The super admin has no company, so counts as active."""
    if company_id is None:
        return True
    company = await get_company(db, company_id)
    return company is not None and company.is_active


async def create_company(db: AsyncSession, name: str) -> Company:
    company = Company(name=name)
    db.add(company)
    await db.commit()
    await db.refresh(company)  # load is_active / timestamps set by the database
    return company


async def update_company(db: AsyncSession, company: Company, changes: dict[str, Any]) -> Company:
    for field, value in changes.items():
        setattr(company, field, value)
    await db.commit()
    await db.refresh(company)  # updated_at is set by the database
    return company
