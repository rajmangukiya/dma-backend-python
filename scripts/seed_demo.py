"""Create the "Demo Logistics" company: one user per role, the freight skeletons
(with match rules) and a journey using them.

Run:  uv run python -m scripts.seed_demo
      uv run python -m scripts.seed_demo --replace-skeletons   (reload skeletons + add the journey)

Skeletons, rules and the journey come from demo_data.json (exported from the Node seed).
"""

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.common.passwords import hash_password
from src.companies import service as companies
from src.companies.models import Company
from src.database import models  # noqa: F401  (registers every table)
from src.database.session import SessionLocal, engine
from src.document_skeletons import service as skeletons
from src.document_skeletons.enums import FieldType
from src.documents import service as documents
from src.journeys import service as journeys
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
DATA = json.loads((Path(__file__).parent / "demo_data.json").read_text())


async def create_users(db: AsyncSession, company: Company) -> None:
    password_hash = await hash_password(PASSWORD)
    db.add_all(
        User(username=username, password=password_hash, role=role, company_id=company.id)
        for username, role in USERS
    )
    await db.commit()


async def create_skeletons(db: AsyncSession, company: Company) -> dict[str, int]:
    """Returns {skeleton key: skeleton id}."""
    skeleton_ids: dict[str, int] = {}
    field_ids: dict[str, int] = {}  # "key|field name" -> field id
    for key, title, document_type, description, fields in DATA["documentSkeletons"]:
        skeleton = await skeletons.create_skeleton(
            db, company.id, title, document_type, description
        )
        skeleton_ids[key] = skeleton.id
        for name, field_type in fields:
            field = await skeletons.create_field(db, skeleton.id, name, FieldType(field_type))
            field_ids[f"{key}|{name}"] = field.id

    for key, name, targets in DATA["matches"]:
        source = await skeletons.get_field(db, skeleton_ids[key], field_ids[f"{key}|{name}"])
        assert source, f"Unknown match source {key} · {name}"
        for target_key, target_name in targets:
            await skeletons.add_match(
                db, source, field_ids[f"{target_key}|{target_name}"], company.id
            )
    return skeleton_ids


async def create_journey(db: AsyncSession, company: Company, skeleton_ids: dict[str, int]) -> None:
    spec = DATA["journey"]
    journey = await journeys.create_journey(db, company.id, spec["title"], spec["description"])
    for segment_name, keys in spec["segments"]:
        segment = await journeys.create_segment(db, journey.id, segment_name)
        for key in keys:
            skeleton = await skeletons.get_skeleton(db, skeleton_ids[key], company.id)
            assert skeleton, f"Unknown skeleton {key}"
            await documents.create_from_skeleton(db, journey.id, segment.id, skeleton)


async def main(replace_skeletons: bool) -> None:
    async with SessionLocal() as db:
        company = await companies.get_company_by_name(db, COMPANY_NAME)
        if company and not replace_skeletons:
            has_skeletons = bool(await skeletons.list_skeletons(db, company.id))
            if has_skeletons:
                print(
                    f'"{COMPANY_NAME}" already exists — run with --replace-skeletons '
                    "to reload its skeletons and add the journey."
                )
                return

        if not company:
            company = await companies.create_company(db, COMPANY_NAME)
            await create_users(db, company)
        else:
            existing = await skeletons.list_skeletons(db, company.id)
            for skeleton in existing:
                await skeletons.delete_skeleton(db, skeleton)
            print(f"Deleted {len(existing)} existing skeletons.")

        skeleton_ids = await create_skeletons(db, company)
        await create_journey(db, company, skeleton_ids)

    rules = sum(len(targets) for _, _, targets in DATA["matches"])
    count = len(DATA["documentSkeletons"])
    print(
        f'Seeded "{COMPANY_NAME}": {count} document skeletons, {rules} match rules, '
        f'journey "{DATA["journey"]["title"]}".'
    )
    print(f"Users (password: {PASSWORD}): " + ", ".join(u for u, _ in USERS))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(replace_skeletons="--replace-skeletons" in sys.argv))
