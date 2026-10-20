"""Auth dependencies used by every protected route: the current user and permission checks."""

from typing import Annotated

from fastapi import Cookie, Depends

from src.auth.permissions import Permission, permissions_for
from src.auth.tokens import decode_token
from src.common.cookies import ACCESS_TOKEN_COOKIE
from src.common.errors import AppError
from src.companies import service as companies
from src.database.session import DbSession
from src.users import service as users
from src.users.models import User


async def get_current_user(
    db: DbSession,
    # Reads the cookie named access_token (None when missing)
    access_token: Annotated[str | None, Cookie(alias=ACCESS_TOKEN_COOKIE)] = None,
) -> User:
    if not access_token:
        raise AppError.unauthorized("Authentication required")

    payload = decode_token(access_token, "access")
    user = await users.get_user(db, int(payload.sub))
    if not user or not user.is_active or user.token_version != payload.token_version:
        raise AppError.unauthorized("Invalid session")
    if not await companies.is_company_active(db, user.company_id):
        raise AppError.unauthorized("Your company account is disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require(*required: Permission):
    """Dependency factory: `dependencies=[Depends(require(Permission.MANAGE_USERS))]`."""

    async def check(user: CurrentUser) -> User:
        granted = permissions_for(user.role)
        if not all(permission in granted for permission in required):
            raise AppError.forbidden()
        return user

    return check


async def get_company_id(user: CurrentUser) -> int:
    """The signed-in user's company; 403 for the super admin, who has none."""
    if user.company_id is None:
        raise AppError.forbidden("This action is only available to company users")
    return user.company_id


CurrentCompanyId = Annotated[int, Depends(get_company_id)]
