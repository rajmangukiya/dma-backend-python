"""Platform super admin (/api/admin)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.enums import UserRole
from tests.conftest import create_company, create_user, login


async def _signed_in_root(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "root", UserRole.SUPER_ADMIN)
    await login(client, "root")


async def test_company_users_cannot_use_admin(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "boss", UserRole.ADMIN, await create_company(db))
    await login(client, "boss")

    assert (await client.get("/api/admin/stats")).status_code == 403


async def test_create_company_with_admin(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)
    body = {"name": " Acme ", "adminUsername": "Acme.Admin", "adminPassword": "long-enough"}

    created = await client.post("/api/admin/companies", json=body)
    duplicate = await client.post("/api/admin/companies", json={**body, "name": "ACME"})

    assert created.status_code == 201
    data = created.json()["data"]
    assert data["name"] == "Acme"
    assert data["isActive"] is True
    assert data["admin"]["username"] == "acme.admin"
    assert data["admin"]["role"] == "admin"
    assert duplicate.status_code == 409
    assert "name" in duplicate.json()["details"]["fieldErrors"]
    # The new admin can sign in
    assert (await login(client, "acme.admin", "long-enough")).status_code == 200


async def test_taken_username_creates_nothing(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)

    response = await client.post(
        "/api/admin/companies",
        json={"name": "Acme", "adminUsername": "root", "adminPassword": "long-enough"},
    )

    assert response.status_code == 409
    assert "adminUsername" in response.json()["details"]["fieldErrors"]
    assert (await client.get("/api/admin/companies")).json()["data"] == []


async def test_list_and_stats_count_per_company(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)
    acme = await create_company(db, "Acme")
    await create_company(db, "Idle", active=False)
    await create_user(db, "a1", UserRole.ADMIN, acme)
    await create_user(db, "a2", UserRole.VIEWER, acme)

    companies = (await client.get("/api/admin/companies")).json()["data"]
    stats = (await client.get("/api/admin/stats")).json()["data"]

    assert [(c["name"], c["userCount"], c["journeyCount"]) for c in companies] == [
        ("Idle", 0, 0),  # newest first
        ("Acme", 2, 0),
    ]
    assert stats == {
        "companies": 2,
        "activeCompanies": 1,
        "users": 2,  # the super admin isn't counted
        "journeys": 0,
        "documents": 0,
        "files": 0,
    }


async def test_disabling_company_signs_its_users_out(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)
    acme = await create_company(db, "Acme")
    await create_user(db, "boss", UserRole.ADMIN, acme)

    updated = await client.patch(f"/api/admin/companies/{acme.id}", json={"isActive": False})

    assert updated.json()["data"]["isActive"] is False
    assert (await login(client, "boss")).status_code == 403


async def test_company_detail_and_not_found(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)
    acme = await create_company(db, "Acme")
    await create_user(db, "boss", UserRole.ADMIN, acme)

    detail = (await client.get(f"/api/admin/companies/{acme.id}")).json()["data"]
    missing = await client.get("/api/admin/companies/999")

    assert [user["username"] for user in detail["users"]] == ["boss"]
    assert "password" not in detail["users"][0]
    assert missing.status_code == 404
    assert missing.json()["message"] == "Company not found"


async def test_super_admin_resets_password_and_role(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_root(client, db)
    acme = await create_company(db, "Acme")
    await create_user(db, "boss", UserRole.ADMIN, acme)
    viewer = await create_user(db, "viewer", UserRole.VIEWER, acme)

    response = await client.patch(
        f"/api/admin/companies/{acme.id}/users/{viewer.id}",
        json={"role": "operations", "password": "brand-new-pass"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "operations"
    assert (await login(client, "viewer", "brand-new-pass")).status_code == 200
