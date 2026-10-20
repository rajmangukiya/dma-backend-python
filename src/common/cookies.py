"""Auth cookie names and options. No token logic here (that is auth/tokens.py)."""

from datetime import datetime

from fastapi import Response

from src.common.config import get_settings

ACCESS_TOKEN_COOKIE = "access_token"
REFRESH_TOKEN_COOKIE = "refresh_token"
# The refresh cookie is only sent to /api/auth/* (refresh, logout)
REFRESH_TOKEN_PATH = "/api/auth"


def _cookie_options() -> dict:
    production = get_settings().is_production
    return {
        "httponly": True,  # JavaScript can't read it
        "secure": production,  # HTTPS only in production
        "samesite": "strict" if production else "lax",
    }


def set_token_cookie(
    response: Response, key: str, value: str, expires_at: datetime, path: str
) -> None:
    response.set_cookie(key, value, expires=expires_at, path=path, **_cookie_options())


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_TOKEN_COOKIE, path="/", **_cookie_options())
    response.delete_cookie(REFRESH_TOKEN_COOKIE, path=REFRESH_TOKEN_PATH, **_cookie_options())
