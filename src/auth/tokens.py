"""JWT access/refresh tokens and the cookies that carry them."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

import jwt
from fastapi import Response
from pydantic import BaseModel

from src.common.config import get_settings
from src.common.cookies import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    REFRESH_TOKEN_PATH,
    set_token_cookie,
)
from src.common.errors import AppError
from src.users.enums import UserRole
from src.users.models import User

TokenKind = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    # User id. Stored as a string in the JWT; parsed back to a UUID, so a token from
    # before the switch to UUIDs (sub="2") fails validation and is rejected as invalid
    sub: UUID
    role: UserRole
    company_id: UUID | None
    token_version: int


def _secret_and_lifetime(kind: TokenKind) -> tuple[str, timedelta]:
    settings = get_settings()
    if kind == "access":
        return settings.jwt_access_secret, timedelta(minutes=settings.jwt_access_expires_minutes)
    return settings.jwt_refresh_secret, timedelta(days=settings.jwt_refresh_expires_days)


def create_token(user: User, kind: TokenKind) -> tuple[str, datetime]:
    """Returns the signed token and its expiry time."""
    secret, lifetime = _secret_and_lifetime(kind)
    expires_at = datetime.now(UTC) + lifetime
    payload = TokenPayload(
        sub=user.id,
        role=user.role,
        company_id=user.company_id,
        token_version=user.token_version,
    ).model_dump(mode="json")
    token = jwt.encode({**payload, "exp": expires_at}, secret, algorithm="HS256")
    return token, expires_at


def decode_token(token: str, kind: TokenKind) -> TokenPayload:
    secret, _ = _secret_and_lifetime(kind)
    try:
        claims = jwt.decode(token, secret, algorithms=["HS256"])
        return TokenPayload.model_validate(claims)
    except Exception as error:  # expired, tampered, wrong secret, malformed...
        raise AppError.unauthorized("Invalid or expired token") from error


def issue_auth_cookies(response: Response, user: User) -> None:
    """Signs fresh access + refresh tokens for `user` and sets them as cookies."""
    access_token, access_expires = create_token(user, "access")
    refresh_token, refresh_expires = create_token(user, "refresh")
    set_token_cookie(response, ACCESS_TOKEN_COOKIE, access_token, access_expires, "/")
    set_token_cookie(
        response, REFRESH_TOKEN_COOKIE, refresh_token, refresh_expires, REFRESH_TOKEN_PATH
    )
