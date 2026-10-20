from src.common.schemas import CamelModel, PatchRequest
from src.companies.schemas import CompanyName, CompanyRead
from src.users.schemas import CompanyRole, Password, PublicUser, Username


class PlatformStats(CamelModel):
    companies: int
    active_companies: int
    users: int
    journeys: int
    documents: int
    files: int


class CompanyListItem(CompanyRead):
    user_count: int
    journey_count: int


class CompanyDetail(CompanyRead):
    users: list[PublicUser]


class CreatedCompany(CompanyRead):
    admin: PublicUser


class CreateCompanyRequest(CamelModel):
    name: CompanyName
    admin_username: Username
    admin_password: Password


class UpdateCompanyRequest(PatchRequest):
    name: CompanyName | None = None
    is_active: bool | None = None


class UpdateCompanyUserRequest(PatchRequest):
    """The super admin can also set a new password in the same request."""

    role: CompanyRole | None = None
    is_active: bool | None = None
    password: Password | None = None
