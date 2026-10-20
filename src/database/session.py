from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from src.common.config import get_settings

settings = get_settings()

# One engine per process: it owns the connection pool
engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,  # replace dead connections (e.g. after Postgres restarts)
    # Tests run each test in its own event loop; pooled asyncpg connections can't
    # cross event loops, so tests open a fresh connection every time instead
    **({"poolclass": NullPool} if settings.environment == "test" else {}),
)

# Factory for sessions. expire_on_commit=False keeps loaded attributes usable
# after commit — with async there is no lazy reload to fall back on
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request, closed when the request ends.

    Use in a route as:  db: AsyncSession = Depends(get_db)
    """
    async with SessionLocal() as session:
        yield session


# Route parameter type: `db: DbSession` gives the route a session for this request
DbSession = Annotated[AsyncSession, Depends(get_db)]
