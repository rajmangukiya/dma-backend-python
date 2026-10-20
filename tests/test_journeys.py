"""Journeys, segments, documents, uploads and matching."""

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.documents.extraction import extraction_runner
from src.users.enums import UserRole
from tests.conftest import create_company, create_user, login


async def _setup(client: AsyncClient, db: AsyncSession) -> dict:
    """An admin with two skeletons (BOL matches Packing List) in a one-segment journey."""
    await create_user(db, "boss", UserRole.ADMIN, await create_company(db))
    await login(client, "boss")

    async def skeleton(title: str, *fields: tuple[str, str]) -> dict:
        data = (
            await client.post(
                "/api/document-skeletons", json={"title": title, "documentType": title}
            )
        ).json()["data"]
        for name, field_type in fields:
            data = (
                await client.post(
                    f"/api/document-skeletons/{data['id']}/fields",
                    json={"name": name, "type": field_type},
                )
            ).json()["data"]
        return data

    packing = await skeleton("Packing List", ("Container no.", "code"))
    bol = await skeleton("BOL", ("Container no.", "code"), ("Shipper", "party"))
    await client.post(
        f"/api/document-skeletons/{bol['id']}/fields/{bol['fields'][0]['id']}/matches",
        json={"matchFieldId": packing["fields"][0]["id"]},
    )

    journey = (await client.post("/api/journeys", json={"title": "FCL Export"})).json()["data"]
    journey = (
        await client.post(f"/api/journeys/{journey['id']}/segments", json={"name": "Loading"})
    ).json()["data"]
    segment_id = journey["segments"][0]["id"]
    for skeleton in (packing, bol):
        journey = (
            await client.post(
                f"/api/segments/{segment_id}/documents", json={"documentSkeletonId": skeleton["id"]}
            )
        ).json()["data"]
    docs = {d["title"]: d["id"] for d in journey["segments"][0]["documents"]}
    return {"journey": journey, "segment_id": segment_id, "docs": docs, "bol": bol}


async def _upload(client: AsyncClient, document_id: int, *names: str):
    files = [("files", (name, b"%PDF-1.4 test", "application/pdf")) for name in names]
    response = await client.post(f"/api/documents/{document_id}/files", files=files)
    await extraction_runner.wait()
    return response


async def test_journey_lifecycle(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)
    journey_id = s["journey"]["id"]

    listed = (await client.get("/api/journeys")).json()["data"][0]
    duplicate = await client.post(f"/api/journeys/{journey_id}/segments", json={"name": "LOADING"})
    again = await client.post(
        f"/api/segments/{s['segment_id']}/documents", json={"documentSkeletonId": s["bol"]["id"]}
    )

    assert (listed["segmentCount"], listed["documentCount"], listed["status"]) == (
        1,
        2,
        "in_progress",
    )
    assert duplicate.status_code == 409
    assert again.status_code == 409
    assert again.json()["message"] == "BOL is already in this segment"


async def test_upload_extracts_and_matches(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)
    bol_id, packing_id = s["docs"]["BOL"], s["docs"]["Packing List"]

    before = (await client.get(f"/api/documents/{bol_id}")).json()["data"]
    uploaded = await _upload(client, bol_id, "bol.pdf", "rider.pdf")
    waiting = (await client.get(f"/api/documents/{bol_id}")).json()["data"]
    await _upload(client, packing_id, "packing.pdf")
    matched = (await client.get(f"/api/documents/{bol_id}")).json()["data"]

    assert before["status"] == "pending"
    assert uploaded.status_code == 201
    assert uploaded.json()["message"] == "2 files uploaded"
    assert waiting["status"] == "ready"
    assert waiting["fields"][0]["checks"][0]["status"] == "awaiting_upload"
    # The dummy extractor gives "Container no." the same value in both documents
    container = matched["fields"][0]
    assert container["result"] == "matched"
    assert container["checks"][0]["targetSegmentName"] == "Loading"
    assert container["sourceFileName"] in {"bol.pdf", "rider.pdf"}
    assert matched["counts"] == {
        "total": 2,
        "extracted": 2,
        "notExtracted": 0,
        "matched": 1,
        "notMatched": 0,
    }
    journey = (await client.get(f"/api/journeys/{s['journey']['id']}")).json()["data"]
    assert journey["stats"] == {"documents": 2, "uploaded": 2, "matched": 1, "notMatched": 0}


async def test_manual_value_overrides_extraction(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)
    bol_id = s["docs"]["BOL"]
    await _upload(client, s["docs"]["Packing List"], "packing.pdf")
    await _upload(client, bol_id, "bol.pdf")
    field_id = (await client.get(f"/api/documents/{bol_id}")).json()["data"]["fields"][0]["id"]

    url = f"/api/documents/{bol_id}/fields/{field_id}/value"
    edited = (await client.put(url, json={"value": "WRONG 1"})).json()["data"]["fields"][0]
    await client.put(url, json={"value": None})
    await extraction_runner.wait()
    restored = (await client.get(f"/api/documents/{bol_id}")).json()["data"]["fields"][0]

    assert (edited["value"], edited["isManual"], edited["result"]) == (
        "WRONG 1",
        True,
        "not_matched",
    )
    assert (restored["isManual"], restored["result"]) == (False, "matched")


async def test_files_download_and_removal(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)
    bol_id = s["docs"]["BOL"]
    data = (await _upload(client, bol_id, "bol.pdf")).json()["data"]
    file_id = data["files"][0]["id"]

    download = await client.get(f"/api/documents/{bol_id}/files/{file_id}/download")
    unsupported = await client.post(
        f"/api/documents/{bol_id}/files", files=[("files", ("evil.exe", b"MZ", "x"))]
    )
    nothing = await client.post(f"/api/documents/{bol_id}/files")
    await client.delete(f"/api/documents/{bol_id}/files/{file_id}")
    await extraction_runner.wait()
    after = (await client.get(f"/api/documents/{bol_id}")).json()["data"]

    assert download.content == b"%PDF-1.4 test"
    assert "storageKey" not in data["files"][0]
    assert unsupported.json()["message"] == "Unsupported file type: evil.exe"
    assert nothing.json()["message"] == "Select at least one file to upload"
    assert (after["status"], after["files"]) == ("pending", [])


async def test_documents_are_company_scoped(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)
    await create_user(db, "rival", UserRole.ADMIN, await create_company(db, "Rival"))
    await login(client, "rival")

    document = await client.get(f"/api/documents/{s['docs']['BOL']}")
    segment = await client.delete(f"/api/segments/{s['segment_id']}")

    assert document.status_code == 404
    assert segment.status_code == 404


async def test_removing_segment_removes_documents(client: AsyncClient, db: AsyncSession) -> None:
    s = await _setup(client, db)

    removed = (await client.delete(f"/api/segments/{s['segment_id']}")).json()["data"]
    gone = await client.get(f"/api/documents/{s['docs']['BOL']}")

    assert removed["segments"] == []
    assert gone.status_code == 404
