"""Document skeletons (/api/document-skeletons)."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users.enums import UserRole
from tests.conftest import create_company, create_user, login


async def _designer(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "designer", UserRole.SKELETON_DESIGNER, await create_company(db))
    await login(client, "designer")


async def _skeleton(client: AsyncClient, title: str, *fields: tuple[str, str]) -> dict:
    data = (
        await client.post(
            "/api/document-skeletons", json={"title": title, "documentType": title.upper()}
        )
    ).json()["data"]
    for name, field_type in fields:
        response = await client.post(
            f"/api/document-skeletons/{data['id']}/fields", json={"name": name, "type": field_type}
        )
        data = response.json()["data"]
    return data


async def test_create_and_edit_skeleton(client: AsyncClient, db: AsyncSession) -> None:
    await _designer(client, db)

    created = await client.post(
        "/api/document-skeletons", json={"title": " Bill of Lading ", "documentType": "BOL"}
    )
    document_skeleton_id = created.json()["data"]["id"]
    empty = await client.post("/api/document-skeletons", json={"title": " ", "documentType": "X"})
    renamed = await client.patch(
        f"/api/document-skeletons/{document_skeleton_id}", json={"description": "Carrier copy"}
    )
    cleared = await client.patch(
        f"/api/document-skeletons/{document_skeleton_id}", json={"description": None}
    )

    assert created.status_code == 201
    assert created.json()["data"]["title"] == "Bill of Lading"
    assert empty.json()["details"]["fieldErrors"] == {"title": ["Title is required"]}
    assert renamed.json()["data"]["description"] == "Carrier copy"
    assert cleared.json()["data"]["description"] is None


async def test_fields_are_unique_per_skeleton(client: AsyncClient, db: AsyncSession) -> None:
    await _designer(client, db)
    bol = await _skeleton(client, "BOL", ("Container no.", "code"))

    duplicate = await client.post(
        f"/api/document-skeletons/{bol['id']}/fields",
        json={"name": "container NO.", "type": "text"},
    )

    assert duplicate.status_code == 409
    assert "name" in duplicate.json()["details"]["fieldErrors"]
    assert [f["position"] for f in bol["fields"]] == [0]


async def test_match_rules(client: AsyncClient, db: AsyncSession) -> None:
    await _designer(client, db)
    packing = await _skeleton(client, "Packing List", ("Container no.", "code"))
    bol = await _skeleton(client, "BOL", ("Container no.", "code"), ("Shipper", "party"))
    bol_container, bol_shipper = bol["fields"]
    target = packing["fields"][0]

    url = f"/api/document-skeletons/{bol['id']}/fields/{bol_container['id']}/matches"
    added = await client.post(url, json={"matchFieldId": target["id"]})
    again = await client.post(url, json={"matchFieldId": target["id"]})
    same_skeleton = await client.post(url, json={"matchFieldId": bol_shipper["id"]})

    assert added.status_code == 201
    assert added.json()["data"]["fields"][0]["matches"] == [
        {
            "fieldId": target["id"],
            "fieldName": "Container no.",
            "documentSkeletonId": packing["id"],
            "documentSkeletonTitle": "Packing List",
        }
    ]
    assert again.status_code == 409
    assert same_skeleton.status_code == 400

    # The packing list sees one incoming rule; the list counts it as BOL's rule
    detail = (await client.get(f"/api/document-skeletons/{packing['id']}")).json()["data"]
    listed = {t["title"]: t for t in (await client.get("/api/document-skeletons")).json()["data"]}
    candidates = (await client.get(f"/api/document-skeletons/{bol['id']}/match-candidates")).json()[
        "data"
    ]
    assert detail["fields"][0]["incomingCount"] == 1
    assert (listed["BOL"]["fieldCount"], listed["BOL"]["ruleCount"]) == (2, 1)
    assert [c["title"] for c in candidates] == ["Packing List"]

    removed = await client.delete(f"{url}/{target['id']}")
    assert removed.json()["data"]["fields"][0]["matches"] == []


async def test_viewers_cannot_edit_skeletons(client: AsyncClient, db: AsyncSession) -> None:
    await create_user(db, "viewer", UserRole.VIEWER, await create_company(db))
    await login(client, "viewer")

    assert (await client.get("/api/document-skeletons")).status_code == 200
    created = await client.post("/api/document-skeletons", json={"title": "X", "documentType": "X"})
    assert created.status_code == 403


async def test_other_company_skeleton_is_not_found(client: AsyncClient, db: AsyncSession) -> None:
    await _designer(client, db)
    other = await _skeleton(client, "BOL")
    await create_user(db, "rival", UserRole.ADMIN, await create_company(db, "Rival"))
    await login(client, "rival")

    response = await client.get(f"/api/document-skeletons/{other['id']}")

    assert response.status_code == 404
    assert response.json()["message"] == "Skeleton not found"
