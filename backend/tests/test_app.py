from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from app.core.config import get_settings
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


def test_cors_preflight_allows_localhost_frontend_origin() -> None:
    client = TestClient(create_app())

    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_preflight_allows_private_network_frontend_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_NETWORK", "")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())

        response = client.options(
            "/healthz",
            headers={
                "Origin": "http://192.168.10.69:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 400
    finally:
        get_settings.cache_clear()


def test_cors_preflight_allows_frontend_origin_within_configured_network(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_NETWORK", "192.168.10.0/24")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())

        response = client.options(
            "/healthz",
            headers={
                "Origin": "http://192.168.10.69:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://192.168.10.69:5173"
    finally:
        get_settings.cache_clear()


def test_cors_preflight_allows_frontend_origin_for_single_host_network(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_NETWORK", "192.168.10.69/32")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())

        response = client.options(
            "/healthz",
            headers={
                "Origin": "http://192.168.10.69:5173",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://192.168.10.69:5173"
    finally:
        get_settings.cache_clear()


def test_cors_preflight_rejects_configured_network_origin_on_unexpected_port(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOW_ORIGIN_NETWORK", "192.168.10.0/24")
    get_settings.cache_clear()
    try:
        client = TestClient(create_app())

        response = client.options(
            "/healthz",
            headers={
                "Origin": "http://192.168.10.69:9999",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 400
    finally:
        get_settings.cache_clear()


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


def test_unknown_route_returns_safe_404_error_envelope_and_request_id() -> None:
    client = TestClient(create_app())

    response = client.get("/missing-route")

    assert response.status_code == 404
    assert response.headers["x-request-id"]
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Not Found",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_method_not_allowed_returns_safe_405_error_envelope_and_request_id() -> None:
    client = TestClient(create_app())

    response = client.post("/healthz")

    assert response.status_code == 405
    assert response.headers["x-request-id"]
    assert response.json() == {
        "error": {
            "code": "method_not_allowed",
            "message": "Method Not Allowed",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_http_exception_returns_retry_hints_for_503_responses() -> None:
    app = create_app()
    router = APIRouter()

    @router.get("/maintenance")
    async def maintenance() -> dict[str, str]:
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable",
            headers={"Retry-After": "30"},
        )

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/maintenance")

    assert response.status_code == 503
    assert response.headers["retry-after"] == "30"
    assert response.json() == {
        "error": {
            "code": "service_unavailable",
            "message": "Service Unavailable",
            "details": {
                "retry_after_seconds": 30,
            },
        },
        "request_id": response.headers["x-request-id"],
    }


def test_http_exception_does_not_echo_unsafe_detail_strings() -> None:
    app = create_app()
    router = APIRouter()

    @router.get("/unsafe-http-detail")
    async def unsafe_http_detail() -> dict[str, str]:
        raise HTTPException(status_code=400, detail="database password missing from /srv/app/.env")

    app.include_router(router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/unsafe-http-detail")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "Bad Request",
        },
        "request_id": response.headers["x-request-id"],
    }

