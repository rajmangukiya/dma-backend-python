from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import get_settings
from app.schemas.common import ErrorResponse


class AppError(Exception):
    """Raise anywhere in the app to return `{ success: false, message }` with a status code."""

    def __init__(self, status_code: int, message: str, details: dict[str, Any] | None = None):
        self.status_code = status_code
        self.message = message
        self.details = details


def _error(status_code: int, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    body = ErrorResponse(message=message, details=details)
    return JSONResponse(status_code=status_code, content=body.model_dump(exclude_none=True))


def _field_errors(exc: RequestValidationError) -> dict[str, Any]:
    """Pydantic errors -> Node's shape: { formErrors: [], fieldErrors: { field: [msg] } }."""
    form_errors: list[str] = []
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        # loc looks like ("body", "username") or ("query", "page"); drop the source
        path = [str(part) for part in error["loc"][1:]]
        if path:
            field_errors.setdefault(".".join(path), []).append(error["msg"])
        else:
            form_errors.append(error["msg"])
    return {"formErrors": form_errors, "fieldErrors": field_errors}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error(exc.status_code, exc.message, exc.details)

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
