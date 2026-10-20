"""Auth business rules. No HTTP here: cookies are the router's job."""

from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.permissions import permissions_for
from src.auth.schemas import ChangePasswordRequest, LoginRequest, SessionUser
from src.auth.tokens import decode_token
from src.common.errors import AppError
from src.common.passwords import hash_password, verify_password
from src.companies import service as companies
from src.companies.schemas import CompanyRef
from src.users import service as users
from src.users.models import User
from src.users.schemas import PublicUser


async def login(db: AsyncSession, body: LoginRequest) -> User:
    user = await users.get_user_by_username(db, body.username)
    if not user or not await verify_password(body.password, user.password):
        raise AppError.unauthorized("Invalid username or password")
    if not user.is_active:
        raise AppError.forbidden("Your account is disabled")
    if not await companies.is_company_active(db, user.company_id):
        raise AppError.forbidden("Your company account is disabled")
    return user


async def refresh(db: AsyncSession, refresh_token: str | None) -> User:
    if not refresh_token:
        raise AppError.unauthorized("Refresh token missing")

    payload = decode_token(refresh_token, "refresh")
    user = await users.get_user(db, payload.sub)
    valid = (
        user is not None
        and user.is_active
        and user.token_version == payload.token_version
        and await companies.is_company_active(db, user.company_id)
    )
    if not valid:
        # The router's response is discarded when we raise, so the error clears the cookies
        raise AppError(401, "Invalid session", clear_auth_cookies=True)
    return user


async def change_password(db: AsyncSession, user: User, body: ChangePasswordRequest) -> None:
    if not await verify_password(body.current_password, user.password):
        raise AppError.bad_request(
            "Current password is incorrect",
            AppError.field("currentPassword", "Current password is incorrect"),
        )
    await users.set_password(db, user, await hash_password(body.new_password))
    await users.bump_token_version(db, user)  # every other session is now invalid


async def build_session(db: AsyncSession, user: User) -> SessionUser:
    """The signed-in user's profile + company + permissions."""
    company = await companies.get_company(db, user.company_id) if user.company_id else None
    return SessionUser(
        **PublicUser.model_validate(user).model_dump(),
        company=CompanyRef.model_validate(company) if company else None,
        permissions=permissions_for(user.role),
    )
