from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.common import ApiResponse, ok

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unreachable"]
    timestamp: datetime


# The return annotation is also the response model: FastAPI validates the
# output against it and shows it in /docs
@router.get("/health")
async def health(
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse[HealthData]:
    try:
        await db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unreachable"
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ok(
        HealthData(
            status="ok" if database == "ok" else "degraded",
            database=database,
            timestamp=datetime.now(UTC),
        )
    )
