"""Database queries for companies."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.companies.models import Company


async def get_company(db: AsyncSession, company_id: int) -> Company | None:
    return await db.get(Company, company_id)


async def is_company_active(db: AsyncSession, company_id: int | None) -> bool:
    """The super admin has no company, so counts as active."""
    if company_id is None:
        return True
    company = await get_company(db, company_id)
    return company is not None and company.is_active
