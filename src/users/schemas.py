from datetime import datetime
from typing import Annotated

from pydantic import Field, StringConstraints

from src.common.schemas import CamelModel
from src.users.enums import UserRole

# Reusable constrained types (also used by auth, and later by admin when creating users)
Password = Annotated[str, Field(min_length=8, max_length=128)]
Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1)]


class PublicUser(CamelModel):
    """A user as returned by the API — never includes the password hash."""

    id: int
    username: str
    role: UserRole
    company_id: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
