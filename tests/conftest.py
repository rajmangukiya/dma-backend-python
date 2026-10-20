"""Shared test setup. pytest loads this file before any test module.

Tests use their own database (dma_py_test), rebuilt once per run and
emptied before every test.
"""

import asyncio
import os
import tempfile

# Must run before `app` is imported: settings are read (and cached) on first use
os.environ["ENVIRONMENT"] = "test"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/dma_py_test"
os.environ["EXTRACTION_DELAY_MS"] = "0"
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="dma-test-uploads-")

from collections.abc import AsyncIterator  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from src.common.passwords import hash_password  # noqa: E402
from src.companies.models import Company  # noqa: E402
from src.database import models as _all_tables  # noqa: E402, F401
from src.database.base import Base  # noqa: E402
from src.database.session import SessionLocal, engine  # noqa: E402
from src.main import app  # noqa: E402
from src.users.enums import UserRole  # noqa: E402
from src.users.models import User  # noqa: E402

PASSWORD = "test-pass-123"


@pytest.fixture(scope="session", autouse=True)
def create_schema() -> None:
    """Drop and recreate every table once per test run (from the models, not migrations)."""

    async def rebuild() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(rebuild())


@pytest.fixture(autouse=True)
async def clean_tables() -> None:
    """Start every test with empty tables and ids from 1."""
    tables = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    async with engine.begin() as connection:
        await connection.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def make_client(cookies: dict[str, str] | None = None) -> AsyncClient:
    """An HTTP client that calls the app in-process (no server needed) and keeps cookies."""
    return AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver", cookies=cookies
    )


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with make_client() as c:
        yield c


# --- Factories -------------------------------------------------------------


async def create_company(db: AsyncSession, name: str = "Acme", *, active: bool = True) -> Company:
    company = Company(name=name, is_active=active)
    db.add(company)
    await db.commit()
    return company


async def create_user(
    db: AsyncSession,
    username: str,
    role: UserRole,
    company: Company | None = None,
    *,
    active: bool = True,
) -> User:
    user = User(
        username=username,
        password=await hash_password(PASSWORD),
        role=role,
        company_id=company.id if company else None,
        is_active=active,
    )
    db.add(user)
    await db.commit()
    return user


async def login(client: AsyncClient, username: str, password: str = PASSWORD):
    return await client.post("/api/auth/login", json={"username": username, "password": password})
