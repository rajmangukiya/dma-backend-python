from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.enums import UserRole
from tests.conftest import PASSWORD, create_company, create_user, login, make_client


async def test_login_sets_cookies_and_returns_session(
    client: AsyncClient, db: AsyncSession
) -> None:
    company = await create_company(db)
    await create_user(db, "jane", UserRole.OPERATIONS, company)

    response = await login(client, " JANE ")  # trimmed and lowercased

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["username"] == "jane"
    assert data["companyId"] == company.id  # camelCase, like the Node API
    assert data["company"] == {"id": company.id, "name": "Acme"}
    assert "journeys:manage" in data["permissions"]
    assert "password" not in data
    assert {"access_token", "refresh_token"} <= set(client.cookies.keys())


async def test_login_rejects_wrong_password(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "jane", UserRole.ADMIN, await create_company(db))

    response = await login(client, "jane", "wrong-password")

    assert response.status_code == 401
    assert response.json()["message"] == "Invalid username or password"


async def test_login_rejects_disabled_company(client: AsyncClient, db: AsyncSession) -> None:
    company = await create_company(db, active=False)
    await create_user(db, "jane", UserRole.ADMIN, company)

    response = await login(client, "jane")

    assert response.status_code == 403


async def test_me_requires_login(client: AsyncClient) -> None:
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["message"] == "Authentication required"


async def test_super_admin_has_no_company(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "root", UserRole.SUPER_ADMIN)
    await login(client, "root")

    data = (await client.get("/api/auth/me")).json()["data"]

    assert data["company"] is None
    assert data["permissions"] == ["companies:manage"]


async def test_refresh_issues_new_session(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "jane", UserRole.VIEWER, await create_company(db))
    await login(client, "jane")

    response = await client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json()["message"] == "Session refreshed"


async def test_change_password_invalidates_other_sessions(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_user(db, "jane", UserRole.VIEWER, await create_company(db))
    await login(client, "jane")
    old_refresh_token = client.cookies["refresh_token"]

    response = await client.patch(
        "/api/auth/change-password",
        json={"currentPassword": PASSWORD, "newPassword": "brand-new-pass"},
    )
    assert response.status_code == 200

    # This client got fresh cookies and stays signed in...
    assert (await client.get("/api/auth/me")).status_code == 200
    # ...but another device still holding the old refresh token is rejected
    async with make_client({"refresh_token": old_refresh_token}) as other_device:
        stale = await other_device.post("/api/auth/refresh")
    assert stale.status_code == 401
    assert (await login(client, "jane", "brand-new-pass")).status_code == 200


async def test_change_password_errors_point_at_fields(
    client: AsyncClient, db: AsyncSession
) -> None:
    await create_user(db, "jane", UserRole.VIEWER, await create_company(db))
    await login(client, "jane")

    wrong = await client.patch(
        "/api/auth/change-password",
        json={"currentPassword": "nope", "newPassword": "brand-new-pass"},
    )
    same = await client.patch(
        "/api/auth/change-password",
        json={"currentPassword": PASSWORD, "newPassword": PASSWORD},
    )

    assert wrong.json()["details"]["fieldErrors"] == {
        "currentPassword": ["Current password is incorrect"]
    }
    assert same.json()["details"]["fieldErrors"] == {
        "newPassword": ["New password must be different from the current password"]
    }


async def test_logout_all_ends_every_session(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "jane", UserRole.VIEWER, await create_company(db))
    await login(client, "jane")
    old_access_token = client.cookies["access_token"]

    await client.post("/api/auth/logout-all")

    async with make_client({"access_token": old_access_token}) as other_device:
        me = await other_device.get("/api/auth/me")
    assert me.status_code == 401
    assert me.json()["message"] == "Invalid session"
