from typing import Annotated

from pydantic import AfterValidator, StringConstraints, ValidationInfo, field_validator

from src.auth.permissions import Permission
from src.common.schemas import CamelModel
from src.companies.schemas import CompanyRef
from src.users.schemas import Password, PublicUser


def _required(message: str):
    def check(value: str) -> str:
        if not value:
            raise ValueError(message)
        return value

    return AfterValidator(check)


# Login accepts any existing username (no new-account rules), just trimmed and lowercased
LoginUsername = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True),
    _required("Username is required"),
]


class LoginRequest(CamelModel):
    username: LoginUsername
    password: Annotated[str, _required("Password is required")]


class ChangePasswordRequest(CamelModel):
    current_password: Annotated[str, _required("Current password is required")]
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
