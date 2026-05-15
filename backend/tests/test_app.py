from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import create_app


def test_healthcheck_returns_ok_and_request_id() -> None:
    client = TestClient(create_app())

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-request-id"]


def test_openapi_includes_health_route() -> None:
    client = TestClient(create_app())

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/healthz" in response.json()["paths"]


def test_cors_preflight_allows_frontend_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_unhandled_exception_returns_safe_error_envelope_and_request_id() -> None:
    app = create_app()
    router = APIRouter()

    @router.get("/boom")
    async def boom() -> dict[str, str]:
        raise RuntimeError("boom")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/boom")

    assert response.status_code == 500
    assert response.headers["x-request-id"]
    assert response.json() == {
        "error": {
            "code": "internal_error",
            "message": "Internal Server Error",
        },
        "request_id": response.headers["x-request-id"],
    }

