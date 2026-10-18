from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.common import ApiResponse, ok

router = APIRouter(tags=["health"])


class HealthData(BaseModel):
    status: str
    timestamp: datetime


# The return annotation is also the response model: FastAPI validates the
# output against it and shows it in /docs
@router.get("/health")
def health() -> ApiResponse[HealthData]:
    return ok(HealthData(status="ok", timestamp=datetime.now(UTC)))
