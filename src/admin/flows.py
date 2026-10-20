"""Super admin use cases. Admin owns no table: each flow chains other modules' services."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.admin.schemas import (
    CompanyListItem,
    CreateCompanyRequest,
    CreatedCompany,
    PlatformStats,
)
from src.common.errors import AppError
from src.companies import service as companies
from src.companies.schemas import CompanyRead
from src.documents import service as documents
from src.journeys import service as journeys
from src.users import service as users
from src.users.enums import UserRole
from src.users.schemas import PublicUser


async def platform_stats(db: AsyncSession) -> PlatformStats:
    # One session runs one query at a time, so these are sequential (no asyncio.gather)
    return PlatformStats(
        companies=await companies.count_companies(db),
        active_companies=await companies.count_companies(db, active_only=True),
        users=await users.count_company_users(db),
        journeys=await journeys.count_journeys(db),
        documents=await documents.count_documents(db),
        files=await documents.count_files(db),
    )


async def list_companies_with_counts(db: AsyncSession) -> list[CompanyListItem]:
    user_counts = await users.count_by_company(db)
    journey_counts = await journeys.count_by_company(db)
    return [
        CompanyListItem(
            **CompanyRead.model_validate(company).model_dump(),
            user_count=user_counts.get(company.id, 0),
            journey_count=journey_counts.get(company.id, 0),
        )
        for company in await companies.list_companies(db)
    ]


async def create_company_with_admin(db: AsyncSession, body: CreateCompanyRequest) -> CreatedCompany:
    """A company always starts with one admin user."""
    # Check both before creating anything, so a taken username doesn't leave an empty company
    if await companies.get_company_by_name(db, body.name):
        message = "A company with that name already exists"
        raise AppError.conflict(message, AppError.field("name", message))
    if await users.get_user_by_username(db, body.admin_username):
        message = "That username is taken"
        raise AppError.conflict(message, AppError.field("adminUsername", message))

    company = await companies.create_company(db, body.name)
    admin = await users.create_user(
        db, company.id, body.admin_username, body.admin_password, UserRole.ADMIN
    )
    return CreatedCompany(
        **CompanyRead.model_validate(company).model_dump(),
        admin=PublicUser.model_validate(admin),
    )
