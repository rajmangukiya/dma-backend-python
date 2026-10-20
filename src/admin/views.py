from fastapi import APIRouter, Depends, status

from src.admin import flows
from src.admin.schemas import (
    CompanyDetail,
    CompanyListItem,
    CreateCompanyRequest,
    CreatedCompany,
    PlatformStats,
    UpdateCompanyRequest,
    UpdateCompanyUserRequest,
)
from src.auth.dependencies import require
from src.auth.permissions import Permission
from src.common.errors import AppError
from src.common.schemas import ApiResponse, ok
from src.companies import service as companies
from src.companies.models import Company
from src.companies.schemas import CompanyRead
from src.database.session import DbSession
from src.users import service as users
from src.users.schemas import CreateUserRequest, PublicUser

# Platform super admin: companies and their users
router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(require(Permission.MANAGE_COMPANIES))]
)


async def _load_company(db: DbSession, company_id: int) -> Company:
    company = await companies.get_company(db, company_id)
    if not company:
        raise AppError.not_found("Company not found")
    return company


@router.get("/stats")
async def stats(db: DbSession) -> ApiResponse[PlatformStats]:
    return ok(await flows.platform_stats(db))


@router.get("/companies")
async def list_companies(db: DbSession) -> ApiResponse[list[CompanyListItem]]:
    return ok(await flows.list_companies_with_counts(db))


@router.post("/companies", status_code=status.HTTP_201_CREATED)
async def create_company(body: CreateCompanyRequest, db: DbSession) -> ApiResponse[CreatedCompany]:
    return ok(await flows.create_company_with_admin(db, body), "Company created")


@router.get("/companies/{company_id}")
async def get_company(company_id: int, db: DbSession) -> ApiResponse[CompanyDetail]:
    company = await _load_company(db, company_id)
    company_users = await users.list_company_users(db, company_id)
    return ok(
        CompanyDetail(
            **CompanyRead.model_validate(company).model_dump(),
            users=[PublicUser.model_validate(user) for user in company_users],
        )
    )


@router.patch("/companies/{company_id}")
async def update_company(
    company_id: int, body: UpdateCompanyRequest, db: DbSession
) -> ApiResponse[CompanyRead]:
    company = await _load_company(db, company_id)
    if body.name:
        existing = await companies.get_company_by_name(db, body.name)
        if existing and existing.id != company_id:
            raise AppError.conflict("A company with that name already exists")
    company = await companies.update_company(db, company, body.changes())
    return ok(CompanyRead.model_validate(company), "Company updated")


@router.post("/companies/{company_id}/users", status_code=status.HTTP_201_CREATED)
async def create_company_user(
    company_id: int, body: CreateUserRequest, db: DbSession
) -> ApiResponse[PublicUser]:
    await _load_company(db, company_id)
    user = await users.create_user(db, company_id, body.username, body.password, body.role)
    return ok(PublicUser.model_validate(user), "User created")


@router.patch("/companies/{company_id}/users/{user_id}")
async def update_company_user(
    company_id: int, user_id: int, body: UpdateCompanyUserRequest, db: DbSession
) -> ApiResponse[PublicUser]:
    user = await users.get_company_user(db, company_id, user_id)
    if not user:
        raise AppError.not_found("User not found")

    changes = body.changes()
    if password := changes.pop("password", None):
        await users.reset_password(db, user, password)
    if changes:
        user = await users.update_user(db, user, changes, actor_id=None)
    return ok(PublicUser.model_validate(user), "User updated")
