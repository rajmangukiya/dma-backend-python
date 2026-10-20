from sqlalchemy import CheckConstraint, ForeignKey, String, true
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base, TimestampMixin, pg_enum
from src.users.enums import UserRole


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        # The super admin is the only user without a company
        CheckConstraint("(role = 'super_admin') = (company_id IS NULL)", name="company_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    # Stored lowercase; unique across the whole platform
    username: Mapped[str] = mapped_column(String(100), unique=True)
    # bcrypt hash — never include it in response schemas
    password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(pg_enum(UserRole, "user_role_enum"))
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), index=True
    )
    is_active: Mapped[bool] = mapped_column(server_default=true())
    # Incremented to invalidate every previously issued token
    token_version: Mapped[int] = mapped_column(server_default="0")
