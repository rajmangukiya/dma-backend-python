from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from src.database.session import get_db
from src.main import app

client = TestClient(app)


# Needs Postgres running (the dma_py database)
def test_health_reports_database_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "ok"
    assert data["database"] == "ok"


class BrokenSession:
    async def execute(self, *_args: object) -> None:
        raise ConnectionError("database is down")


async def broken_db() -> AsyncIterator[BrokenSession]:
    yield BrokenSession()


def test_health_reports_database_down() -> None:
    # Swap the real dependency for a fake one, only for this test
    app.dependency_overrides[get_db] = broken_db
    try:
        response = client.get("/api/health")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["data"] == {
        "status": "degraded",
        "database": "unreachable",
        "timestamp": response.json()["data"]["timestamp"],
    }
