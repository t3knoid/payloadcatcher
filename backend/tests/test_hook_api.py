from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session


def _build_test_app(*, hook_payload_max_bytes: int = 1024) -> tuple[FastAPI, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = create_app()
    settings = Settings(
        _env_file=None,
        trusted_proxies=["testclient"],
        hook_payload_max_bytes=hook_payload_max_bytes,
    )

    def override_db_session() -> Generator[Session, None, None]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings
    return app, testing_session_factory


def _seed_inbox(session_factory: sessionmaker[Session], clsid: str) -> None:
    now = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    with session_factory() as session:
        session.add(
            Inbox(
                clsid=clsid,
                source_ip="203.0.113.10",
                issued_at=now,
                expires_at=now + timedelta(hours=24),
            )
        )
        session.commit()


def test_post_hook_accepts_json_and_persists_event() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440000"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    response = client.post(
        f"/hook/{clsid}",
        json={"foo": "bar", "count": 2},
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    request_id = response.json()["request_id"]

    with session_factory() as session:
        event = session.scalar(select(WebhookEvent).where(WebhookEvent.request_id == request_id))

    assert event is not None
    assert event.content_type == "application/json"
    assert json.loads(event.payload_raw.decode("utf-8")) == {"foo": "bar", "count": 2}
    assert "foo: bar" in event.payload_yaml


def test_post_hook_accepts_form_payload() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440001"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    response = client.post(
        f"/hook/{clsid}",
        data={"foo": "bar", "count": "2"},
        headers={"x-forwarded-for": "198.51.100.8"},
    )

    assert response.status_code == 200
    request_id = response.json()["request_id"]

    with session_factory() as session:
        event = session.scalar(select(WebhookEvent).where(WebhookEvent.request_id == request_id))

    assert event is not None
    assert event.content_type == "application/x-www-form-urlencoded"
    assert event.payload_raw.decode("utf-8") in {
        "foo=bar&count=2",
        "count=2&foo=bar",
    }
    assert "foo:" in event.payload_yaml


def test_post_hook_accepts_binary_payload() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440002"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)
    payload = b"\x00\x01payload\xff"

    response = client.post(
        f"/hook/{clsid}",
        content=payload,
        headers={
            "content-type": "application/octet-stream",
            "x-forwarded-for": "198.51.100.9",
        },
    )

    assert response.status_code == 200
    request_id = response.json()["request_id"]

    with session_factory() as session:
        event = session.scalar(select(WebhookEvent).where(WebhookEvent.request_id == request_id))

    assert event is not None
    assert event.content_type == "application/octet-stream"
    assert event.payload_raw == payload
    assert "payload_size_bytes" in event.payload_yaml


def test_post_hook_returns_safe_404_for_unknown_inbox() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.post(
        "/hook/550e8400-e29b-41d4-a716-446655440099",
        json={"foo": "bar"},
    )

    assert response.status_code == 404
    assert response.headers["x-request-id"]
    assert response.json() == {
        "error": {
            "code": "inbox_not_found",
            "message": "Inbox not found or expired",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_post_hook_returns_413_for_oversized_payload() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440003"
    app, session_factory = _build_test_app(hook_payload_max_bytes=4)
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    response = client.post(
        f"/hook/{clsid}",
        content=b"12345",
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 413
    assert response.json() == {
        "error": {
            "code": "payload_too_large",
            "message": "Payload exceeds configured size limit",
            "details": {
                "max_bytes": 4,
            },
        },
        "request_id": response.headers["x-request-id"],
    }


def test_post_hook_returns_415_for_invalid_content_type() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440004"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    response = client.post(
        f"/hook/{clsid}",
        content=b"payload",
        headers={"content-type": "not-a-media-type"},
    )

    assert response.status_code == 415
    assert response.json() == {
        "error": {
            "code": "unsupported_media_type",
            "message": "Content-Type header is invalid",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_openapi_includes_hook_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/hook/{clsid}" in response.json()["paths"]