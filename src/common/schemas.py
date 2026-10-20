from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for API schemas: snake_case in Python, camelCase in JSON (like the Node API).

    - `alias_generator`: company_id <-> "companyId"
    - `populate_by_name`: accept either name when building a model in Python
    - `from_attributes`: build from SQLAlchemy objects, e.g. PublicUser.model_validate(user)
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


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
