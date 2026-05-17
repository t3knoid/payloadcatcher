from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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
    rate_limit_per_minute: int = 60,
    viewer_payload_preview_chars: int = 4096,
) -> tuple[FastAPI, sessionmaker[Session]]:
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
        rate_limit_per_minute=rate_limit_per_minute,
        viewer_payload_preview_chars=viewer_payload_preview_chars,
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


def _seed_inbox_with_events(
    session_factory: sessionmaker[Session],
    clsid: str,
    *,
    expired: bool = False,
) -> None:
    issued_at = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    expires_at = issued_at + timedelta(hours=24)
    if expired:
        expires_at = issued_at - timedelta(minutes=1)

    with session_factory() as session:
        inbox = Inbox(
            clsid=clsid,
            source_ip="203.0.113.10",
            issued_at=issued_at,
            expires_at=expires_at,
        )
        session.add(inbox)
        session.flush()

        events = [
            WebhookEvent(
                inbox_id=inbox.id,
                request_id="evt-newest",
                received_at=datetime(2026, 5, 15, 12, 3, tzinfo=UTC),
                method="POST",
                content_type="application/json",
                headers_json={"content-type": "application/json"},
                payload_raw=b'{"message":"latest"}',
                payload_size_bytes=20,
                payload_encoding=None,
                payload_yaml="message: latest\n",
                source_ip="203.0.113.10",
                dedup_key=None,
                is_duplicate=False,
            ),
            WebhookEvent(
                inbox_id=inbox.id,
                request_id="evt-middle",
                received_at=datetime(2026, 5, 15, 12, 2, tzinfo=UTC),
                method="PATCH",
                content_type="text/plain",
                headers_json={"content-type": "text/plain"},
                payload_raw=b"unsafe-yaml-payload",
                payload_size_bytes=19,
                payload_encoding=None,
                payload_yaml="!!python/object/apply:os.system ['echo nope']\n",
                source_ip="198.51.100.18",
                dedup_key=None,
                is_duplicate=False,
            ),
            WebhookEvent(
                inbox_id=inbox.id,
                request_id="evt-oldest",
                received_at=datetime(2026, 5, 15, 12, 1, tzinfo=UTC),
                method="POST",
                content_type="application/x-www-form-urlencoded",
                headers_json={"content-type": "application/x-www-form-urlencoded"},
                payload_raw=b"foo=bar",
                payload_size_bytes=7,
                payload_encoding=None,
                payload_yaml="form_value: searchable-preview\n",
                source_ip="2001:db8::1234",
                dedup_key=None,
                is_duplicate=False,
            ),
        ]
        session.add_all(events)
        session.commit()


def test_get_inbox_returns_masked_sorted_paginated_events() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440100"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(
        f"/api/inboxes/{clsid}?limit=2",
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["hook_url"].endswith(f"/hook/{clsid}")
    assert payload["metadata"]["capture_count"] == 3
    assert len(payload["events"]) == 2
    assert [event["request_id"] for event in payload["events"]] == ["evt-newest", "evt-middle"]
    assert payload["events"][0]["source_ip_masked"] == "203.0.113.0/24"
    assert payload["events"][1]["source_ip_masked"] == "198.51.100.0/24"
    assert payload["events"][1]["payload_yaml"] == "!!python/object/apply:os.system ['echo nope']\n"
    assert payload["next_token"]


def test_get_inbox_uses_cursor_for_next_page() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440101"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    first_page = client.get(f"/api/inboxes/{clsid}?limit=2")

    assert first_page.status_code == 200
    next_token = first_page.json()["next_token"]
    second_page = client.get(f"/api/inboxes/{clsid}?limit=2&cursor={next_token}")

    assert second_page.status_code == 200
    assert [event["request_id"] for event in second_page.json()["events"]] == ["evt-oldest"]
    assert second_page.json()["events"][0]["source_ip_masked"] == "2001:db8::/64"
    assert second_page.json()["next_token"] is None


def test_get_inbox_filters_search_text_across_request_fields() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440102"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(f"/api/inboxes/{clsid}?q=searchable-preview")

    assert response.status_code == 200
    assert [event["request_id"] for event in response.json()["events"]] == ["evt-oldest"]


def test_get_inbox_returns_safe_errors_for_invalid_limits_and_expired_inbox() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440103"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid, expired=True)
    client = TestClient(app)

    invalid_limit = client.get(f"/api/inboxes/{clsid}?limit=101")
    expired_response = client.get(f"/api/inboxes/{clsid}")

    assert invalid_limit.status_code == 400
    assert invalid_limit.json() == {
        "error": {
            "code": "invalid_limit",
            "message": "limit must be between 1 and 100",
        },
        "request_id": invalid_limit.headers["x-request-id"],
    }
    assert expired_response.status_code == 404
    assert expired_response.json() == {
        "error": {
            "code": "inbox_not_found",
            "message": "Inbox not found or expired",
        },
        "request_id": expired_response.headers["x-request-id"],
    }


def test_get_inbox_returns_400_for_invalid_cursor() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440104"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(f"/api/inboxes/{clsid}?cursor=not-a-valid-token")

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "invalid_cursor",
            "message": "cursor is invalid",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_get_inbox_returns_422_for_non_integer_limit_query() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440110"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(f"/api/inboxes/{clsid}?limit=abc")

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": {
                "errors": [
                    {
                        "loc": ["query", "limit"],
                        "msg": "Input should be a valid integer, unable to parse string as an integer",
                        "type": "int_parsing",
                    }
                ],
            },
        },
        "request_id": response.headers["x-request-id"],
    }


def test_get_inbox_returns_429_with_retry_hints_when_rate_limited() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440105"
    app, session_factory = _build_test_app(rate_limit_per_minute=1)
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    first_response = client.get(
        f"/api/inboxes/{clsid}",
        headers={"x-forwarded-for": "203.0.113.10"},
    )
    second_response = client.get(
        f"/api/inboxes/{clsid}",
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


def test_get_inbox_event_detail_returns_full_payload_and_headers() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440106"
    app, session_factory = _build_test_app(viewer_payload_preview_chars=10)
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(f"/api/inboxes/{clsid}/events/evt-middle")

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "evt-middle",
        "received_at": "2026-05-15T12:02:00Z",
        "method": "PATCH",
        "content_type": "text/plain",
        "headers": {"content-type": "text/plain"},
        "payload_yaml": "!!python/object/apply:os.system ['echo nope']\n",
        "source_ip_masked": "198.51.100.0/24",
        "payload_size_bytes": 19,
    }


def test_get_inbox_event_detail_returns_safe_404_for_missing_event() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440107"
    app, session_factory = _build_test_app()
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    response = client.get(f"/api/inboxes/{clsid}/events/missing-request")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "event_not_found",
            "message": "Event not found for inbox",
        },
        "request_id": response.headers["x-request-id"],
    }


def test_get_inbox_event_detail_uses_independent_rate_limit_budget_from_listing() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440108"
    app, session_factory = _build_test_app(rate_limit_per_minute=1)
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    listing_response = client.get(
        f"/api/inboxes/{clsid}",
        headers={"x-forwarded-for": "203.0.113.10"},
    )
    detail_response = client.get(
        f"/api/inboxes/{clsid}/events/evt-middle",
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert listing_response.status_code == 200
    assert detail_response.status_code == 200


def test_get_inbox_event_detail_returns_429_with_retry_hints_when_detail_budget_is_exhausted() -> None:
    clsid = "550e8400-e29b-41d4-a716-446655440109"
    app, session_factory = _build_test_app(rate_limit_per_minute=1)
    _seed_inbox_with_events(session_factory, clsid)
    client = TestClient(app)

    first_response = client.get(
        f"/api/inboxes/{clsid}/events/evt-middle",
        headers={"x-forwarded-for": "203.0.113.10"},
    )
    second_response = client.get(
        f"/api/inboxes/{clsid}/events/evt-middle",
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


def test_openapi_includes_inbox_viewer_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/api/inboxes/{clsid}" in response.json()["paths"]
    assert "/api/inboxes/{clsid}/events/{request_id}" in response.json()["paths"]