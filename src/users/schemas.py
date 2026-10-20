import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator

from src.common.schemas import CamelModel, PatchRequest
from src.users.enums import UserRole

_USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]+$")


def _check_username(value: str) -> str:
    value = value.strip().lower()
    if len(value) < 3:
        raise ValueError("Username must be at least 3 characters")
    if len(value) > 100:
        raise ValueError("Username must be at most 100 characters")
    if not _USERNAME_PATTERN.match(value):
        raise ValueError("Use letters, numbers, dots, dashes or underscores")
    return value


def _check_password(value: str) -> str:
    if len(value) < 8:
        raise ValueError("Password must be at least 8 characters")
    if len(value) > 128:
        raise ValueError("Password must be at most 128 characters")
    return value


# Reusable constrained types for new accounts (same rules and messages as the Node API).
# Validators that raise ValueError report just their message on the field.
Username = Annotated[str, AfterValidator(_check_username)]
Password = Annotated[str, AfterValidator(_check_password)]
# Any role except super_admin
CompanyRole = Literal[
    UserRole.ADMIN, UserRole.SKELETON_DESIGNER, UserRole.OPERATIONS, UserRole.VIEWER
]


class PublicUser(CamelModel):
    """A user as returned by the API — never includes the password hash."""

    id: UUID
    username: str
    role: UserRole
    company_id: UUID | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreateUserRequest(CamelModel):
    username: Username
    password: Password
    role: CompanyRole


class UpdateUserRequest(PatchRequest):
    role: CompanyRole | None = None
    is_active: bool | None = None


class ResetPasswordRequest(CamelModel):
    password: Password
