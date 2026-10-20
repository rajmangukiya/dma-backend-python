from src.common.schemas import CamelModel


class CompanyRef(CamelModel):
    """The short form of a company, embedded in other responses."""

    id: int
    name: str
