"""Create the "Demo Logistics" company with one user per role.

Run:  uv run python -m scripts.seed_demo
(Skeletons and the freight journey are added once those APIs are ported.)
"""

import asyncio

from sqlalchemy import select

from src.common.passwords import hash_password
from src.companies.models import Company
from src.database.session import SessionLocal, engine
from src.users.enums import UserRole
from src.users.models import User

COMPANY_NAME = "Demo Logistics"
PASSWORD = "demo-pass-123"
USERS = [
    ("demo.admin", UserRole.ADMIN),
    ("demo.designer", UserRole.SKELETON_DESIGNER),
    ("demo.ops", UserRole.OPERATIONS),
    ("demo.viewer", UserRole.VIEWER),
]


async def main() -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(Company).where(Company.name == COMPANY_NAME))
        if existing:
            print(f'"{COMPANY_NAME}" already exists — nothing to do.')
            return

        company = Company(name=COMPANY_NAME)
        db.add(company)
        await db.flush()  # sends the INSERT so company.id is available, without committing

        password_hash = await hash_password(PASSWORD)
        db.add_all(
            User(username=username, password=password_hash, role=role, company_id=company.id)
            for username, role in USERS
        )
        await db.commit()

    print(f'Created "{COMPANY_NAME}". Sign in with (password: {PASSWORD}):')
    for username, role in USERS:
        print(f"  {username:<15} {role.value}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
