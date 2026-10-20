from datetime import datetime
from typing import Annotated

from pydantic import StringConstraints

from src.common.schemas import CamelModel

CompanyName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=150)]


class CompanyRef(CamelModel):
    """The short form of a company, embedded in other responses."""

    id: int
    name: str


class CompanyRead(CamelModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
