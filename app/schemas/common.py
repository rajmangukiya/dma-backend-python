from typing import Any

from pydantic import BaseModel


# Same envelope as the Node API: { success, message, data }.
# Generic: ApiResponse[HealthData] means `data` is validated as HealthData.
class ApiResponse[T](BaseModel):
    success: bool = True
    message: str = "Success"
    data: T


class ErrorResponse(BaseModel):
    success: bool = False
    message: str
    details: dict[str, Any] | None = None


def ok[T](data: T, message: str = "Success") -> ApiResponse[T]:
    return ApiResponse(data=data, message=message)
