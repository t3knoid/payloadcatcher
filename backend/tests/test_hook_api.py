from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import json
from math import ceil
from pathlib import Path
import tempfile
from time import perf_counter, sleep
import uuid

import anyio
from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.api.routes.hook import ingest_webhook
from app.infrastructure.rate_limit import InMemoryRateLimiter, get_hook_rate_limiter
from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session
from app.services.webhook_ingestion import PreparedWebhookIngestion


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


@pytest.mark.anyio
async def test_post_hook_burst_ack_latency_stays_within_target() -> None:
    concurrent_requests = 32
    persist_delay_seconds = 0.1
    p95_target_seconds = 0.025
    max_target_seconds = 0.05
    clsid = "550e8400-e29b-41d4-a716-446655440010"
    body = b'{"ok": true}'
    latencies: list[float] = []
    background_batches: list[BackgroundTasks] = []

    def build_request() -> Request:
        delivered = False

        async def receive() -> dict[str, object]:
            nonlocal delivered
            if delivered:
                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }
            delivered = True
            return {
                "type": "http.request",
                "body": body,
                "more_body": False,
            }

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": f"/hook/{clsid}",
                "headers": [],
                "client": ("203.0.113.10", 12345),
            },
            receive,
        )

    async def invoke(index: int) -> None:
        request = build_request()
        prepared = PreparedWebhookIngestion(
            inbox_id=uuid.uuid4(),
            clsid=clsid,
            request_id=f"request-{index}",
            received_at=datetime.now(UTC),
            source_ip=f"203.0.113.{index + 10}",
            method="POST",
            content_type="application/json",
            payload_raw=body,
            payload_encoding=None,
            headers_json={},
        )
        background_tasks = BackgroundTasks()

        class SlowPersistenceService:
            def __init__(self) -> None:
                self.persist_calls = 0

            def prepare_ingestion(
                self,
                incoming_clsid: str,
                incoming_request: Request,
                payload_raw: bytes,
            ) -> PreparedWebhookIngestion:
                assert incoming_clsid == clsid
                assert incoming_request is request
                assert payload_raw == body
                return prepared

            def persist_ingestion(self, prepared_ingestion: PreparedWebhookIngestion) -> None:
                self.persist_calls += 1
                sleep(persist_delay_seconds)
                assert prepared_ingestion is prepared

        service = SlowPersistenceService()
        started = perf_counter()
        response = await ingest_webhook(clsid, request, background_tasks, service)
        latencies.append(perf_counter() - started)

        assert response.status == "accepted"
        assert response.request_id == prepared.request_id
        assert service.persist_calls == 0
        assert len(background_tasks.tasks) == 1
        background_batches.append(background_tasks)

    async with anyio.create_task_group() as task_group:
        for index in range(concurrent_requests):
            task_group.start_soon(invoke, index)

    ordered_latencies = sorted(latencies)
    p95_latency = ordered_latencies[ceil(len(ordered_latencies) * 0.95) - 1]
    max_latency = ordered_latencies[-1]

    assert p95_latency < p95_target_seconds
    assert max_latency < max_target_seconds

    async with anyio.create_task_group() as task_group:
        for background_tasks in background_batches:
            task_group.start_soon(background_tasks)


@pytest.mark.anyio
async def test_post_hook_defers_persistence_to_background_tasks() -> None:
    body = b'{"ok": true}'

    async def receive() -> dict[str, object]:
        return {
            "type": "http.request",
            "body": body,
            "more_body": False,
        }

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/hook/550e8400-e29b-41d4-a716-446655440009",
            "headers": [],
            "client": ("203.0.113.10", 12345),
        },
        receive,
    )
    prepared = PreparedWebhookIngestion(
        inbox_id=uuid.uuid4(),
        clsid="550e8400-e29b-41d4-a716-446655440009",
        request_id="request-123",
        received_at=datetime.now(UTC),
        source_ip="203.0.113.10",
        method="POST",
        content_type="application/json",
        payload_raw=body,
        payload_encoding=None,
        headers_json={},
    )
    background_tasks = BackgroundTasks()

    class StubWebhookService:
        def __init__(self) -> None:
            self.persist_calls: list[PreparedWebhookIngestion] = []

        def prepare_ingestion(self, clsid: str, incoming_request: Request, payload_raw: bytes) -> PreparedWebhookIngestion:
            assert clsid == prepared.clsid
            assert incoming_request is request
            assert payload_raw == body
            return prepared

        def persist_ingestion(self, prepared_ingestion: PreparedWebhookIngestion) -> None:
            self.persist_calls.append(prepared_ingestion)

    service = StubWebhookService()

    response = await ingest_webhook(prepared.clsid, request, background_tasks, service)

    assert response.status == "accepted"
    assert response.request_id == prepared.request_id
    assert service.persist_calls == []
    assert len(background_tasks.tasks) == 1

    await background_tasks()

    assert service.persist_calls == [prepared]


def test_openapi_includes_hook_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/hook/{clsid}" in response.json()["paths"]