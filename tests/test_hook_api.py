from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import anyio
import json
from pathlib import Path
import tempfile
from threading import Event
from time import perf_counter, sleep
from typing import cast
import uuid

from fastapi import BackgroundTasks
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.types import Message

from app.api.routes.hook import ingest_webhook
from app.infrastructure.rate_limit import InMemoryRateLimiter, get_hook_rate_limiter
from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import Inbox, WebhookEvent
from app.persistence.session import get_db_session
from app.services.webhook_ingestion import PreparedWebhookIngestion, WebhookIngestionService


def _build_test_app(
    *,
    hook_payload_max_bytes: int = 1024,
    rate_limit_per_minute: int = 60,
    database_url: str = "sqlite+pysqlite:///:memory:",
    use_static_pool: bool = True,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> tuple[FastAPI, sessionmaker[Session]]:
    engine_kwargs: dict[str, object] = {"connect_args": {"check_same_thread": False}}
    if use_static_pool:
        engine_kwargs["poolclass"] = StaticPool
    else:
        if pool_size is not None:
            engine_kwargs["pool_size"] = pool_size
        if max_overflow is not None:
            engine_kwargs["max_overflow"] = max_overflow
    engine = create_engine(database_url, **engine_kwargs)
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = create_app()
    settings = Settings.model_validate(
        {
            "TRUSTED_PROXIES": ["testclient"],
            "HOOK_PAYLOAD_MAX_BYTES": hook_payload_max_bytes,
            "RATE_LIMIT_PER_MINUTE": rate_limit_per_minute,
        }
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
async def test_post_hook_burst_requests_send_responses_before_slow_background_persistence(monkeypatch) -> None:
    concurrent_requests = 8
    persist_delay_seconds = 0.25
    clsid = "550e8400-e29b-41d4-a716-446655440010"
    persist_delay_ms = persist_delay_seconds * 1000
    persisted_request_ids: list[str] = []
    background_started = Event()
    background_finished = Event()

    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "hook-latency.db"
        app, session_factory = _build_test_app(
            rate_limit_per_minute=100,
            database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
            use_static_pool=False,
            pool_size=concurrent_requests,
            max_overflow=0,
        )

        try:
            _seed_inbox(session_factory, clsid)

            def slow_persist(self: WebhookIngestionService, prepared: PreparedWebhookIngestion) -> None:
                background_started.set()
                sleep(persist_delay_seconds)
                persisted_request_ids.append(prepared.request_id)
                if len(persisted_request_ids) == concurrent_requests:
                    background_finished.set()

            monkeypatch.setattr(WebhookIngestionService, "persist_ingestion", slow_persist)

            async def run_request(index: int) -> tuple[float, float, dict[str, object]]:
                response_messages: list[Message] = []
                response_sent = anyio.Event()
                app_completed = anyio.Event()
                response_sent_at: float | None = None
                app_completed_at: float | None = None
                body = json.dumps({"index": index}).encode("utf-8")
                body_delivered = False

                async def receive() -> dict[str, object]:
                    nonlocal body_delivered
                    if body_delivered:
                        return {
                            "type": "http.request",
                            "body": b"",
                            "more_body": False,
                        }

                    body_delivered = True
                    return {
                        "type": "http.request",
                        "body": body,
                        "more_body": False,
                    }

                async def send(message: Message) -> None:
                    nonlocal response_sent_at
                    response_messages.append(message)
                    if message["type"] == "http.response.body" and not message.get("more_body", False):
                        response_sent_at = perf_counter()
                        response_sent.set()

                async def invoke_app() -> None:
                    nonlocal app_completed_at
                    await app(
                        {
                            "type": "http",
                            "asgi": {"version": "3.0"},
                            "http_version": "1.1",
                            "method": "POST",
                            "scheme": "http",
                            "path": f"/hook/{clsid}",
                            "raw_path": f"/hook/{clsid}".encode("ascii"),
                            "query_string": b"",
                            "root_path": "",
                            "headers": [
                                (b"content-type", b"application/json"),
                                (b"x-forwarded-for", f"203.0.113.{index + 10}".encode("ascii")),
                            ],
                            "client": ("testclient", 12345),
                            "server": ("testserver", 80),
                        },
                        receive,
                        send,
                    )
                    app_completed_at = perf_counter()
                    app_completed.set()

                started_at = perf_counter()

                async with anyio.create_task_group() as task_group:
                    task_group.start_soon(invoke_app)

                    await response_sent.wait()
                    assert response_sent_at is not None
                    assert not app_completed.is_set()

                    await anyio.sleep(persist_delay_seconds / 5)

                    assert background_started.is_set()
                    assert not app_completed.is_set()

                    await app_completed.wait()

                response_start = next(
                    message
                    for message in response_messages
                    if message["type"] == "http.response.start"
                )
                response_body = b"".join(
                    cast(bytes, message.get("body", b""))
                    for message in response_messages
                    if message["type"] == "http.response.body"
                )
                response_payload = json.loads(response_body.decode("utf-8"))
                assert response_sent_at is not None
                assert app_completed_at is not None
                assert response_start["status"] == 200
                assert response_payload["status"] == "accepted"
                return (
                    (response_sent_at - started_at) * 1000,
                    (app_completed_at - started_at) * 1000,
                    response_payload,
                )

            results: list[tuple[float, float, dict[str, object]]] = []

            async def collect_request(index: int) -> None:
                results.append(await run_request(index))

            async with anyio.create_task_group() as task_group:
                for index in range(concurrent_requests):
                    task_group.start_soon(collect_request, index)

            response_send_times_ms = sorted(result[0] for result in results)
            app_completion_times_ms = sorted(result[1] for result in results)
            response_payloads = [result[2] for result in results]
            response_request_ids = [cast(str, payload["request_id"]) for payload in response_payloads]
            p95_index = max(0, (concurrent_requests * 95 + 99) // 100 - 1)

            assert background_finished.is_set()
            assert len(set(response_request_ids)) == concurrent_requests
            assert sorted(response_request_ids) == sorted(persisted_request_ids)
            assert response_send_times_ms[p95_index] < persist_delay_ms * 0.5
            assert response_send_times_ms[-1] < persist_delay_ms * 0.75
            assert app_completion_times_ms[0] >= persist_delay_ms * 0.75
        finally:
            session_factory.kw["bind"].dispose()


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

    response = await ingest_webhook(prepared.clsid, request, background_tasks, cast(WebhookIngestionService, service))

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