from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from src.auth import service
from src.auth.dependencies import CurrentUser
from src.auth.schemas import ChangePasswordRequest, LoginRequest, SessionUser
from src.auth.tokens import issue_auth_cookies
from src.common.cookies import REFRESH_TOKEN_COOKIE, clear_auth_cookies
from src.common.schemas import ApiResponse, ok
from src.database.session import DbSession
from src.users import service as users

# No self-registration: users are created by a company admin or the super admin
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login(body: LoginRequest, response: Response, db: DbSession) -> ApiResponse[SessionUser]:
    user = await service.login(db, body)
    issue_auth_cookies(response, user)
    return ok(await service.build_session(db, user), "Logged in successfully")


@router.post("/refresh")
async def refresh(
    response: Response,
    db: DbSession,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_TOKEN_COOKIE)] = None,
) -> ApiResponse[SessionUser]:
    user = await service.refresh(db, refresh_token)
    issue_auth_cookies(response, user)
    return ok(await service.build_session(db, user), "Session refreshed")


@router.post("/logout")
async def logout(response: Response) -> ApiResponse[None]:
    clear_auth_cookies(response)
    return ok(None, "Logged out successfully")


# Invalidates refresh tokens on every device
@router.post("/logout-all")
async def logout_all(response: Response, user: CurrentUser, db: DbSession) -> ApiResponse[None]:
    await users.bump_token_version(db, user)
    clear_auth_cookies(response)
    return ok(None, "Logged out from all devices")


@router.get("/me")
async def me(user: CurrentUser, db: DbSession) -> ApiResponse[SessionUser]:
    return ok(await service.build_session(db, user))


@router.patch("/change-password")
async def change_password(
    body: ChangePasswordRequest, response: Response, user: CurrentUser, db: DbSession
) -> ApiResponse[None]:
    await service.change_password(db, user, body)
    issue_auth_cookies(response, user)  # fresh tokens for this device
    return ok(None, "Password changed successfully")
