from typing import Any, ClassVar

from pydantic import AfterValidator, BaseModel, ConfigDict, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base for API schemas: snake_case in Python, camelCase in JSON (like the Node API).

    - `alias_generator`: company_id <-> "companyId"
    - `populate_by_name`: accept either name when building a model in Python
    - `from_attributes`: build from SQLAlchemy objects, e.g. PublicUser.model_validate(user)
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


def trimmed(max_length: int, *, required: str | None = None) -> AfterValidator:
    """Validator for a string field: trims it and checks its length.

    Usage: `Title = Annotated[str, trimmed(200, required="Title is required")]`
    `required` is the error message when the value is empty (omit to allow "").
    """

    def check(value: str) -> str:
        value = value.strip()
        if required and not value:
            raise ValueError(required)
        if len(value) > max_length:
            raise ValueError(f"Must be at most {max_length} characters")
        return value

    return AfterValidator(check)


class PatchRequest(CamelModel):
    """Base for PATCH bodies: every field optional, but the body can't be empty.

    Declare fields as `X | None = None`. Fields listed in `nullable` may be sent
    as null to clear them; for any other field, null is treated as "not sent".
    """

    nullable: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def at_least_one_field(self):
        if not self.changes():
            raise ValueError("At least one field is required")
        return self

    def changes(self) -> dict[str, Any]:
        """Only the fields the client actually sent, as {python_name: value}."""
        sent = self.model_dump(exclude_unset=True)
        return {k: v for k, v in sent.items() if v is not None or k in self.nullable}


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
