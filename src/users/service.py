"""Database queries for users."""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.models import User


async def get_user(db: AsyncSession, user_id: int) -> User | None:
    return await db.get(User, user_id)


async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    result = await db.execute(select(User).where(User.username == username.strip().lower()))
    return result.scalar_one_or_none()


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
    await db.refresh(user)
