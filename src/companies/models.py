from uuid import UUID

from sqlalchemy import String, true
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin, new_id


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    is_active: Mapped[bool] = mapped_column(server_default=true())
