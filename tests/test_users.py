"""Company admin managing their own company's users (/api/users)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.enums import UserRole
from tests.conftest import create_company, create_user, login


async def _signed_in_admin(client: AsyncClient, db: AsyncSession):
    company = await create_company(db)
    admin = await create_user(db, "boss", UserRole.ADMIN, company)
    await login(client, "boss")
    return company, admin


async def test_lists_only_own_company(client: AsyncClient, db: AsyncSession) -> None:
    company, _ = await _signed_in_admin(client, db)
    await create_user(db, "ops", UserRole.OPERATIONS, company)
    await create_user(db, "stranger", UserRole.ADMIN, await create_company(db, "Other"))

    data = (await client.get("/api/users")).json()["data"]

    assert [user["username"] for user in data] == ["boss", "ops"]


async def test_requires_manage_users_permission(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "viewer", UserRole.VIEWER, await create_company(db))
    await login(client, "viewer")

    response = await client.get("/api/users")

    assert response.status_code == 403


async def test_create_validates_like_node(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_admin(client, db)

    bad = await client.post(
        "/api/users", json={"username": "a b", "password": "short", "role": "super_admin"}
    )
    good = await client.post(
        "/api/users",
        json={"username": " New.Ops ", "password": "long-enough", "role": "operations"},
    )
    taken = await client.post(
        "/api/users", json={"username": "new.ops", "password": "long-enough", "role": "viewer"}
    )

    assert bad.status_code == 400
    assert set(bad.json()["details"]["fieldErrors"]) == {"username", "password", "role"}
    assert good.status_code == 201
    assert good.json()["data"]["username"] == "new.ops"
    assert taken.status_code == 409


async def test_update_requires_a_field(client: AsyncClient, db: AsyncSession) -> None:
    company, _ = await _signed_in_admin(client, db)
    ops = await create_user(db, "ops", UserRole.OPERATIONS, company)

    response = await client.patch(f"/api/users/{ops.id}", json={})

    assert response.status_code == 400
    assert response.json()["details"]["formErrors"] == ["At least one field is required"]


async def test_cannot_change_own_role(client: AsyncClient, db: AsyncSession) -> None:
    _, admin = await _signed_in_admin(client, db)

    response = await client.patch(f"/api/users/{admin.id}", json={"role": "viewer"})

    assert response.status_code == 400
    assert response.json()["message"] == "You cannot change your own role or status"


async def test_keeps_one_active_admin(client: AsyncClient, db: AsyncSession) -> None:
    company, _ = await _signed_in_admin(client, db)
    second = await create_user(db, "second", UserRole.ADMIN, company)

    # Two admins: demoting one is fine...
    assert (
        await client.patch(f"/api/users/{second.id}", json={"role": "viewer"})
    ).status_code == 200
    # ...but the super admin can't then disable the last one
    await create_user(db, "root", UserRole.SUPER_ADMIN)
    await login(client, "root")
    boss = (await client.get(f"/api/admin/companies/{company.id}")).json()["data"]["users"][0]
    response = await client.patch(
        f"/api/admin/companies/{company.id}/users/{boss['id']}", json={"isActive": False}
    )
    assert response.status_code == 400
    assert response.json()["message"] == "A company needs at least one active admin"


async def test_other_company_user_is_not_found(client: AsyncClient, db: AsyncSession) -> None:
    await _signed_in_admin(client, db)
    stranger = await create_user(db, "stranger", UserRole.VIEWER, await create_company(db, "Other"))

    response = await client.delete(f"/api/users/{stranger.id}")

    assert response.status_code == 404
    assert response.json()["message"] == "User not found"


async def test_reset_password_and_delete(client: AsyncClient, db: AsyncSession) -> None:
    company, admin = await _signed_in_admin(client, db)
    ops = await create_user(db, "ops", UserRole.OPERATIONS, company)

    reset = await client.put(f"/api/users/{ops.id}/password", json={"password": "fresh-pass-1"})
    self_delete = await client.delete(f"/api/users/{admin.id}")
    deleted = await client.delete(f"/api/users/{ops.id}")

    assert reset.json()["message"] == "Password updated"
    assert self_delete.json()["message"] == "You cannot delete your own account"
    assert deleted.json() == {"success": True, "message": "User deleted", "data": None}
