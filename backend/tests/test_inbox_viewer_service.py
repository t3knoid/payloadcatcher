from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.errors import ApiError
from app.api.schemas.inbox import InboxViewerQuery
from app.core.config import Settings
from app.persistence.base import Base
from app.persistence.models import Inbox, WebhookEvent
from app.services.inbox_viewer import InboxViewerService


def _build_session() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def _build_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/inbox/550e8400-e29b-41d4-a716-446655440110",
            "headers": [],
            "client": ("198.51.100.20", 12345),
        }
    )


def _seed_inbox_and_events(session: Session, clsid: str) -> None:
    issued_at = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    inbox = Inbox(
        clsid=clsid,
        source_ip="198.51.100.20",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=24),
    )
    session.add(inbox)
    session.flush()
    session.add_all(
        [
            WebhookEvent(
                inbox_id=inbox.id,
                request_id="evt-search-me",
                received_at=datetime(2026, 5, 15, 12, 3, tzinfo=UTC),
                method="POST",
                content_type="application/json",
                headers_json={},
                payload_raw=b"{}",
                payload_size_bytes=2,
                payload_encoding=None,
                payload_yaml="message: find-me\n",
                source_ip="203.0.113.10",
                dedup_key=None,
                is_duplicate=False,
            ),
            WebhookEvent(
                inbox_id=inbox.id,
                request_id="evt-other",
                received_at=datetime(2026, 5, 15, 12, 2, tzinfo=UTC),
                method="PATCH",
                content_type="text/plain",
                headers_json={},
                payload_raw=b"plain",
                payload_size_bytes=5,
                payload_encoding=None,
                payload_yaml="message: other\n",
                source_ip="198.51.100.8",
                dedup_key=None,
                is_duplicate=False,
            ),
        ]
    )
    session.commit()


def test_get_inbox_view_filters_by_search_text() -> None:
    session = _build_session()
    clsid = "550e8400-e29b-41d4-a716-446655440110"
    _seed_inbox_and_events(session, clsid)
    service = InboxViewerService(session=session, settings=Settings(_env_file=None), rate_limiter=None)

    result = service.get_inbox_view(clsid, InboxViewerQuery(q="find-me"), _build_request())

    assert [event.request_id for event in result.events] == ["evt-search-me"]
    assert result.metadata.capture_count == 2


@pytest.mark.parametrize("limit", [0, 101])
def test_validate_limit_rejects_out_of_range_values(limit: int) -> None:
    session = _build_session()
    service = InboxViewerService(session=session, settings=Settings(_env_file=None), rate_limiter=None)

    with pytest.raises(ApiError) as exc_info:
        service.validate_limit(limit)

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "invalid_limit"


def test_decode_cursor_rejects_invalid_token() -> None:
    session = _build_session()
    service = InboxViewerService(session=session, settings=Settings(_env_file=None), rate_limiter=None)

    with pytest.raises(ApiError) as exc_info:
        service.decode_cursor("not-a-valid-token")

    assert exc_info.value.status_code == 400
    assert exc_info.value.error_code == "invalid_cursor"


def test_mask_source_ip_and_truncate_preview() -> None:
    session = _build_session()
    settings = Settings(_env_file=None, viewer_payload_preview_chars=10)
    service = InboxViewerService(session=session, settings=settings, rate_limiter=None)

    assert service.mask_source_ip("203.0.113.25") == "203.0.113.0/24"
    assert service.mask_source_ip("2001:db8::1234") == "2001:db8::/64"
    assert service.truncate_payload_yaml("1234567890ABC") == "1234567..."


@pytest.mark.parametrize(
    ("preview_chars", "expected_preview"),
    [
        (4, "a..."),
        (5, "ab..."),
    ],
)
def test_truncate_payload_yaml_respects_small_valid_preview_limits(
    preview_chars: int,
    expected_preview: str,
) -> None:
    session = _build_session()
    settings = Settings(_env_file=None, viewer_payload_preview_chars=preview_chars)
    service = InboxViewerService(session=session, settings=settings, rate_limiter=None)

    assert service.truncate_payload_yaml("abcdef") == expected_preview


def test_get_inbox_view_search_uses_visible_preview_text() -> None:
    session = _build_session()
    clsid = "550e8400-e29b-41d4-a716-446655440111"
    issued_at = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    inbox = Inbox(
        clsid=clsid,
        source_ip="198.51.100.20",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=24),
    )
    session.add(inbox)
    session.flush()
    session.add(
        WebhookEvent(
            inbox_id=inbox.id,
            request_id="evt-truncated",
            received_at=datetime(2026, 5, 15, 12, 4, tzinfo=UTC),
            method="POST",
            content_type="text/plain",
            headers_json={},
            payload_raw=b"plain",
            payload_size_bytes=5,
            payload_encoding=None,
            payload_yaml="prefix-aaaaaaaaaaaaaaaaaaaa-needle",
            source_ip="203.0.113.10",
            dedup_key=None,
            is_duplicate=False,
        )
    )
    session.commit()
    service = InboxViewerService(
        session=session,
        settings=Settings(_env_file=None, viewer_payload_preview_chars=10),
        rate_limiter=None,
    )

    hidden_match = service.get_inbox_view(clsid, InboxViewerQuery(q="needle"), _build_request())
    visible_match = service.get_inbox_view(clsid, InboxViewerQuery(q="prefix"), _build_request())

    assert hidden_match.events == []
    assert [event.request_id for event in visible_match.events] == ["evt-truncated"]
    assert visible_match.events[0].payload_yaml == "prefix-..."


def test_get_inbox_event_detail_returns_full_payload_and_headers() -> None:
    session = _build_session()
    clsid = "550e8400-e29b-41d4-a716-446655440112"
    issued_at = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    inbox = Inbox(
        clsid=clsid,
        source_ip="198.51.100.20",
        issued_at=issued_at,
        expires_at=issued_at + timedelta(hours=24),
    )
    session.add(inbox)
    session.flush()
    full_payload = "prefix-aaaaaaaaaaaaaaaaaaaa-needle"
    session.add(
        WebhookEvent(
            inbox_id=inbox.id,
            request_id="evt-detail",
            received_at=datetime(2026, 5, 15, 12, 5, tzinfo=UTC),
            method="POST",
            content_type="application/json",
            headers_json={"content-type": "application/json", "x-trace-id": "trace-123"},
            payload_raw=b'{"payload":"full"}',
            payload_size_bytes=18,
            payload_encoding=None,
            payload_yaml=full_payload,
            source_ip="203.0.113.10",
            dedup_key=None,
            is_duplicate=False,
        )
    )
    session.commit()
    service = InboxViewerService(
        session=session,
        settings=Settings(_env_file=None, viewer_payload_preview_chars=10),
        rate_limiter=None,
    )

    detail = service.get_inbox_event_detail(clsid, "evt-detail", _build_request())
    summary = service.get_inbox_view(clsid, InboxViewerQuery(), _build_request())

    assert detail.request_id == "evt-detail"
    assert detail.payload_yaml == full_payload
    assert detail.headers == {"content-type": "application/json", "x-trace-id": "trace-123"}
    assert detail.source_ip_masked == "203.0.113.0/24"
    assert detail.payload_size_bytes == 18
    assert summary.events[0].payload_yaml == "prefix-..."


def test_get_inbox_event_detail_rejects_missing_request_id() -> None:
    session = _build_session()
    clsid = "550e8400-e29b-41d4-a716-446655440113"
    _seed_inbox_and_events(session, clsid)
    service = InboxViewerService(session=session, settings=Settings(_env_file=None), rate_limiter=None)

    with pytest.raises(ApiError) as exc_info:
        service.get_inbox_event_detail(clsid, "missing-request", _build_request())

    assert exc_info.value.status_code == 404
    assert exc_info.value.error_code == "event_not_found"