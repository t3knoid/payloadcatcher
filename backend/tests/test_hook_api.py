from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.rate_limit import InMemoryRateLimiter, get_hook_rate_limiter
from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session


def _build_test_app(
    *,
    hook_payload_max_bytes: int = 1024,
    rate_limit_per_minute: int = 60,
    database_url: str = "sqlite+pysqlite:///:memory:",
    use_static_pool: bool = True,
) -> tuple[FastAPI, sessionmaker[Session]]:
    engine_kwargs = {"connect_args": {"check_same_thread": False}}
    if use_static_pool:
        engine_kwargs["poolclass"] = StaticPool
    engine = create_engine(database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = create_app()
    settings = Settings(
        _env_file=None,
        trusted_proxies=["testclient"],
        hook_payload_max_bytes=hook_payload_max_bytes,
        rate_limit_per_minute=rate_limit_per_minute,
    )
    limiter = InMemoryRateLimiter(rate_limit_per_minute)

    def override_db_session() -> Generator[Session, None, None]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_hook_rate_limiter] = lambda: limiter
    return app, testing_session_factory


def _seed_inbox(session_factory: sessionmaker[Session], clsid: str) -> None:
    now = datetime.now(UTC)
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


def test_post_hook_persists_malformed_json_with_text_preview() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440005"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)
    payload = b'{"foo": }'

    response = client.post(
        f"/hook/{clsid}",
        content=payload,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    request_id = response.json()["request_id"]

    with session_factory() as session:
        event = session.scalar(select(WebhookEvent).where(WebhookEvent.request_id == request_id))

    assert event is not None
    assert event.payload_raw == payload
    assert "text: '{\"foo\": }'" in event.payload_yaml


def test_post_hook_uses_server_generated_request_id_instead_of_caller_header() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440006"
    app, session_factory = _build_test_app()
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    first_response = client.post(
        f"/hook/{clsid}",
        json={"index": 1},
        headers={"x-request-id": "caller-supplied-id"},
    )
    second_response = client.post(
        f"/hook/{clsid}",
        json={"index": 2},
        headers={"x-request-id": "caller-supplied-id"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.headers["x-request-id"] == "caller-supplied-id"
    assert second_response.headers["x-request-id"] == "caller-supplied-id"
    assert first_response.json()["request_id"] != "caller-supplied-id"
    assert second_response.json()["request_id"] != "caller-supplied-id"
    assert first_response.json()["request_id"] != second_response.json()["request_id"]

    with session_factory() as session:
        persisted_ids = [
            row[0]
            for row in session.query(WebhookEvent.request_id)
            .order_by(WebhookEvent.received_at.asc(), WebhookEvent.id.asc())
            .all()
        ]

    assert persisted_ids == [
        first_response.json()["request_id"],
        second_response.json()["request_id"],
    ]


def test_post_hook_returns_429_with_retry_hints_when_rate_limited() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440007"
    app, session_factory = _build_test_app(rate_limit_per_minute=1)
    _seed_inbox(session_factory, clsid)
    client = TestClient(app)

    first_response = client.post(
        f"/hook/{clsid}",
        json={"ok": True},
        headers={"x-forwarded-for": "203.0.113.10"},
    )
    second_response = client.post(
        f"/hook/{clsid}",
        json={"ok": False},
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert int(second_response.headers["retry-after"]) >= 1
    assert second_response.json() == {
        "error": {
            "code": "rate_limited",
            "message": "Too many requests",
            "details": {
                "retry_after_seconds": int(second_response.headers["retry-after"]),
            },
        },
        "request_id": second_response.headers["x-request-id"],
    }

    with session_factory() as session:
        assert session.query(WebhookEvent).count() == 1


def test_post_hook_persists_concurrent_requests_without_data_loss() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440008"
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "hook-concurrency.db"
        app, session_factory = _build_test_app(
            rate_limit_per_minute=100,
            database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
            use_static_pool=False,
        )
        _seed_inbox(session_factory, clsid)

        def post_event(index: int) -> tuple[int, str]:
            with TestClient(app) as client:
                response = client.post(
                    f"/hook/{clsid}",
                    json={"index": index},
                    headers={"x-forwarded-for": f"203.0.113.{index + 10}"},
                )
            return response.status_code, response.json()["request_id"]

        with ThreadPoolExecutor(max_workers=6) as executor:
            results = list(executor.map(post_event, range(6)))

        assert [status for status, _ in results] == [200, 200, 200, 200, 200, 200]
        request_ids = [request_id for _, request_id in results]
        assert len(set(request_ids)) == 6

        with session_factory() as session:
            persisted_request_ids = {
                row[0]
                for row in session.query(WebhookEvent.request_id)
                .order_by(WebhookEvent.id.asc())
                .all()
            }

        assert persisted_request_ids == set(request_ids)
        session_factory.kw["bind"].dispose()


def test_openapi_includes_hook_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/hook/{clsid}" in response.json()["paths"]