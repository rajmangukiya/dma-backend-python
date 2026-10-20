from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

from src.common.errors import AppError, register_error_handlers


# A throwaway app with routes that fail on purpose, to test the error shapes
def make_client() -> TestClient:
    app = FastAPI()
    register_error_handlers(app)

    class SignupBody(BaseModel):
        username: str = Field(min_length=3)
        password: str = Field(min_length=8)

    @app.post("/signup")
    def signup(body: SignupBody) -> dict:
        return {"username": body.username}

    @app.get("/conflict")
    def conflict() -> None:
        raise AppError(409, "That username is taken")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("something broke")

    return TestClient(app, raise_server_exceptions=False)


client = make_client()


def test_validation_error_uses_node_shape() -> None:
    response = client.post("/signup", json={"username": "ab"})

    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Validation failed"
    assert set(body["details"]["fieldErrors"]) == {"username", "password"}


def test_app_error_keeps_status_and_message() -> None:
    response = client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {"success": False, "message": "That username is taken"}


def test_unknown_route_is_404() -> None:
    response = client.get("/nope")

    assert response.status_code == 404
    assert response.json()["message"] == "Route not found: GET /nope"


def test_unexpected_error_is_500() -> None:
    response = client.get("/boom")

    assert response.status_code == 500
    assert response.json()["success"] is False
