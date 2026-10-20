"""Create the platform super admin from SUPER_ADMIN_USERNAME / SUPER_ADMIN_PASSWORD.

Run:  uv run python -m scripts.seed_super_admin
"""

import asyncio

from src.common.config import get_settings
from src.common.passwords import hash_password
from src.database import models  # noqa: F401  (registers every table)
from src.database.session import SessionLocal, engine
from src.users.enums import UserRole
from src.users.models import User
from src.users.service import get_user_by_username


async def main() -> None:
    settings = get_settings()
    username, password = settings.super_admin_username, settings.super_admin_password
    if not username or not password:
        raise SystemExit("Set SUPER_ADMIN_USERNAME and SUPER_ADMIN_PASSWORD in .env first")

    async with SessionLocal() as db:
        if await get_user_by_username(db, username):
            print(f'Super admin "{username}" already exists — nothing to do.')
            return
        db.add(
            User(
                username=username.lower(),
                password=await hash_password(password),
                role=UserRole.SUPER_ADMIN,
                company_id=None,
            )
        )
        await db.commit()
        print(f'Super admin "{username}" created.')
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
