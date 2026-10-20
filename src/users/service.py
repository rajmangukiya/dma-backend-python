"""Users: reads, writes and the rules for managing a company's users.

Shared by the company admin (/users) and the super admin (/admin/companies/{id}/users).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.common.errors import AppError
from src.common.passwords import hash_password
from src.users.enums import UserRole
from src.users.models import User

# --- Reads -----------------------------------------------------------------


async def get_user(db: AsyncSession, user_id: UUID) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username.strip().lower()))
    return result.scalar_one_or_none()


async def get_company_user(db: AsyncSession, company_id: UUID, user_id: UUID) -> User | None:
    """A user, but only if they belong to `company_id`."""
    user = await get_user(db, user_id)
    return user if user and user.company_id == company_id else None


async def list_company_users(db: AsyncSession, company_id: UUID) -> list[User]:
    result = await db.scalars(
        select(User).where(User.company_id == company_id).order_by(User.created_at)
    )
    return list(result)


async def count_by_company(db: AsyncSession) -> dict[UUID, int]:
    """{company_id: number of users}; companies without users are missing."""
    result = await db.execute(
        select(User.company_id, func.count())
        .where(User.company_id.is_not(None))
        .group_by(User.company_id)
    )
    return dict(result.all())


async def count_company_users(db: AsyncSession) -> int:
    """Every user except the platform super admin."""
    return (
        await db.scalar(
            select(func.count()).select_from(User).where(User.role != UserRole.SUPER_ADMIN)
        )
        or 0
    )


async def _count_active_admins(db: AsyncSession, company_id: UUID) -> int:
    return (
        await db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.company_id == company_id, User.role == UserRole.ADMIN, User.is_active)
        )
        or 0
    )


# --- Writes ----------------------------------------------------------------


async def create_user(
    db: AsyncSession, company_id: UUID, username: str, password: str, role: UserRole
) -> User:
    """`username` already normalised by the request schema; `password` is plain text."""
    if await get_user_by_username(db, username):
        raise AppError.conflict("That username is taken")
    user = User(
        username=username,
        password=await hash_password(password),
        role=role,
        company_id=company_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # load is_active / timestamps set by the database
    return user


async def update_user(
    db: AsyncSession, user: User, changes: dict[str, Any], actor_id: UUID | None
) -> User:
    """Change role and/or is_active. `actor_id`: who is making the change (None = super admin)."""
    if actor_id == user.id:
        raise AppError.bad_request("You cannot change your own role or status")

    loses_admin = (
        user.role == UserRole.ADMIN
        and user.is_active
        and (
            changes.get("role", UserRole.ADMIN) != UserRole.ADMIN
            or changes.get("is_active") is False
        )
    )
    if loses_admin:
        await _ensure_not_last_admin(db, user.company_id)

    for field, value in changes.items():
        setattr(user, field, value)
    await db.commit()
    # Role or status changes take effect on the user's next request
    await bump_token_version(db, user)
    return user


async def reset_password(db: AsyncSession, user: User, password: str) -> None:
    await set_password(db, user, await hash_password(password))
    await bump_token_version(db, user)  # signs the user out everywhere


async def delete_user(db: AsyncSession, user: User, actor_id: UUID) -> None:
    if actor_id == user.id:
        raise AppError.bad_request("You cannot delete your own account")
    if user.role == UserRole.ADMIN and user.is_active:
        await _ensure_not_last_admin(db, user.company_id)
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()


async def set_password(db: AsyncSession, user: User, password_hash: str) -> None:
    user.password = password_hash
    await db.commit()


async def bump_token_version(db: AsyncSession, user: User) -> None:
    """Invalidates every token issued to this user so far."""
    # Done in SQL (token_version + 1) so concurrent requests can't lose an increment
    await db.execute(
        update(User).where(User.id == user.id).values(token_version=User.token_version + 1)
    )
    await db.commit()
    # Reload: token_version and updated_at were changed by the database, not by Python
    await db.refresh(user)


async def _ensure_not_last_admin(db: AsyncSession, company_id: UUID | None) -> None:
    if company_id is not None and await _count_active_admins(db, company_id) <= 1:
        raise AppError.bad_request("A company needs at least one active admin")
