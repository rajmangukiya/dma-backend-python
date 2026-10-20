from typing import Annotated

from pydantic import Field, ValidationInfo, field_validator

from src.auth.permissions import Permission
from src.common.schemas import CamelModel
from src.companies.schemas import CompanyRef
from src.users.schemas import Password, PublicUser, Username


class LoginRequest(CamelModel):
    username: Username
    password: Annotated[str, Field(min_length=1)]


class ChangePasswordRequest(CamelModel):
    current_password: Annotated[str, Field(min_length=1)]
    new_password: Password

    # A field validator, so the error is reported on newPassword (shown next to that input).
    # info.data holds the fields validated before this one (current_password).
    @field_validator("new_password")
    @classmethod
    def new_password_differs(cls, value: str, info: ValidationInfo) -> str:
        if value == info.data.get("current_password"):
            raise ValueError("New password must be different from the current password")
        return value


class SessionUser(PublicUser):
    """Returned by login, refresh and /auth/me."""

    company: CompanyRef | None
    permissions: list[Permission]
