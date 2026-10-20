from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.common.config import get_settings
from src.common.cookies import clear_auth_cookies
from src.common.schemas import ErrorResponse


class AppError(Exception):
    """Raise anywhere in the app to return `{ success: false, message }` with a status code."""

    def __init__(
        self,
        status_code: int,
        message: str,
        details: dict[str, Any] | None = None,
        *,
        clear_auth_cookies: bool = False,  # e.g. a refresh with an invalid session
    ):
        self.status_code = status_code
        self.message = message
        self.details = details
        self.clear_auth_cookies = clear_auth_cookies

    # Shortcuts for the common cases: raise AppError.not_found("Journey not found")
    @classmethod
    def bad_request(cls, message: str, details: dict[str, Any] | None = None) -> "AppError":
        return cls(400, message, details)

    @classmethod
    def unauthorized(cls, message: str = "Authentication required") -> "AppError":
        return cls(401, message)

    @classmethod
    def forbidden(
        cls, message: str = "You do not have permission to perform this action"
    ) -> "AppError":
        return cls(403, message)

    @classmethod
    def not_found(cls, message: str = "Not found") -> "AppError":
        return cls(404, message)

    @classmethod
    def conflict(cls, message: str, details: dict[str, Any] | None = None) -> "AppError":
        return cls(409, message, details)

    @staticmethod
    def field(name: str, message: str) -> dict[str, Any]:
        """`details` that the frontend shows next to one form field."""
        return {"formErrors": [], "fieldErrors": {name: [message]}}


def _error(status_code: int, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    body = ErrorResponse(message=message, details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


def _field_errors(exc: RequestValidationError) -> dict[str, Any]:
    """Pydantic errors -> Node's shape: { formErrors: [], fieldErrors: { field: [msg] } }."""
    form_errors: list[str] = []
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        # Our own `raise ValueError(...)` in validators: show just its text,
        # without Pydantic's "Value error, " prefix
        if error["type"] == "value_error":
            message = str(error["ctx"]["error"])
        else:
            message = error["msg"]
        # loc looks like ("body", "username") or ("query", "page"); drop the source
        path = [str(part) for part in error["loc"][1:]]
        if path:
            field_errors.setdefault(".".join(path), []).append(message)
        else:
            form_errors.append(message)
    return {"formErrors": form_errors, "fieldErrors": field_errors}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        response = _error(exc.status_code, exc.message, exc.details)
        if exc.clear_auth_cookies:
            clear_auth_cookies(response)
        return response

    # Invalid body / query / path params (FastAPI's default is 422; Node returned 400)
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _error(400, "Validation failed", _field_errors(exc))

    # Unknown routes (404), wrong method (405) and any raised HTTPException
    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404 and exc.detail == "Not Found":
            return _error(404, f"Route not found: {request.method} {request.url.path}")
        return _error(exc.status_code, str(exc.detail))

    # Anything unexpected: log it, hide internals in production
    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        print(f"Unhandled error: {exc!r}")
        message = "Internal server error" if get_settings().is_production else str(exc)
        return _error(500, message)
