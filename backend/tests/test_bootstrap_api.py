from __future__ import annotations

from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import re
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.rate_limit import InMemoryRateLimiter, get_request_rate_limiter
from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import VisitMetadata
from app.persistence.session import get_db_session


UUID4_LOWERCASE_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _build_test_app(
    *,
    trusted_proxies: list[str] | None = None,
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
        trusted_proxies=trusted_proxies or ["127.0.0.1", "::1"],
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
    app.dependency_overrides[get_request_rate_limiter] = lambda: limiter
    return app, testing_session_factory


def test_first_visit_sets_cookie_and_revisit_reuses_active_inbox(monkeypatch) -> None:
    first_seen = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.inbox_provisioning.utc_now",
        lambda: first_seen,
    )
    app, session_factory = _build_test_app()
    client = TestClient(app, base_url="https://testserver")

    first_response = client.get(
        "/?timezone=UTC",
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/136.0.0.0 Safari/537.36",
            "referer": "https://www.payloadcat.ch",
            "accept-language": "en-US,en;q=0.9",
            "x-forwarded-for": "203.0.113.10",
        },
    )

    assert first_response.status_code == 200
    assert "payloadcatcher_session=" in first_response.headers["set-cookie"]
    first_payload = first_response.json()
    assert first_payload["new_session"] is True
    assert UUID4_LOWERCASE_PATTERN.match(first_payload["clsid"])
    assert first_payload["callback_url"] == f"https://payloadcat.ch/hook/{first_payload['clsid']}"
    assert first_payload["viewer_url"] == f"https://payloadcat.ch/inbox/{first_payload['clsid']}"
    assert first_payload["expires_at"] == "2026-05-16T12:00:00Z"

    second_response = client.get("/")

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["new_session"] is False
    assert second_payload["clsid"] == first_payload["clsid"]
    assert second_payload["callback_url"] == first_payload["callback_url"]
    assert second_payload["viewer_url"] == first_payload["viewer_url"]
    assert second_payload["expires_at"] == first_payload["expires_at"]

    with session_factory() as session:
        assert session.query(VisitMetadata).count() == 2


def test_expired_session_rotates_to_new_inbox(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 5, 15, 12, 0, tzinfo=UTC)}

    monkeypatch.setattr(
        "app.services.inbox_provisioning.utc_now",
        lambda: current_time["value"],
    )
    app, _ = _build_test_app()
    client = TestClient(app, base_url="https://testserver")

    first_response = client.get("/")
    first_payload = first_response.json()

    current_time["value"] = current_time["value"] + timedelta(hours=25)
    second_response = client.get("/")
    second_payload = second_response.json()

    assert second_response.status_code == 200
    assert second_payload["new_session"] is True
    assert second_payload["clsid"] != first_payload["clsid"]
    assert second_payload["callback_url"] != first_payload["callback_url"]
    assert second_payload["viewer_url"] != first_payload["viewer_url"]


def test_exact_expiration_boundary_rotates_inbox(monkeypatch) -> None:
    current_time = {"value": datetime(2026, 5, 15, 12, 0, tzinfo=UTC)}

    monkeypatch.setattr(
        "app.services.inbox_provisioning.utc_now",
        lambda: current_time["value"],
    )
    app, _ = _build_test_app()
    client = TestClient(app, base_url="https://testserver")

    first_response = client.get("/")
    first_payload = first_response.json()

    current_time["value"] = current_time["value"] + timedelta(hours=24)
    second_response = client.get("/")
    second_payload = second_response.json()

    assert second_response.status_code == 200
    assert second_payload["new_session"] is True
    assert second_payload["clsid"] != first_payload["clsid"]
    assert second_payload["callback_url"] != first_payload["callback_url"]
    assert second_payload["viewer_url"] != first_payload["viewer_url"]


def test_revisit_from_new_ip_keeps_callback_stable_and_records_new_source_ip(monkeypatch) -> None:
    first_seen = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.inbox_provisioning.utc_now",
        lambda: first_seen,
    )
    app, session_factory = _build_test_app(trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    first_response = client.get(
        "/",
        headers={
            "x-forwarded-for": "203.0.113.10",
        },
    )
    first_payload = first_response.json()

    second_response = client.get(
        "/",
        headers={
            "x-forwarded-for": "198.51.100.8",
        },
    )
    second_payload = second_response.json()

    assert second_response.status_code == 200
    assert second_payload["new_session"] is False
    assert second_payload["clsid"] == first_payload["clsid"]

    with session_factory() as session:
        source_ips = [
            row[0]
            for row in session.query(VisitMetadata.source_ip)
            .order_by(VisitMetadata.visited_at.asc(), VisitMetadata.id.asc())
            .all()
        ]

    assert sorted(source_ips) == ["198.51.100.8", "203.0.113.10"]


def test_visit_metadata_persists_gps_consent_and_trusted_locality(monkeypatch) -> None:
    first_seen = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(
        "app.services.inbox_provisioning.utc_now",
        lambda: first_seen,
    )
    app, session_factory = _build_test_app(trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    response = client.get(
        "/",
        params={
            "timezone": "America/New_York",
        },
        headers={
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/136.0.0.0 Safari/537.36",
            "referer": "https://www.payloadcat.ch/privacy",
            "accept-language": "en-US,en;q=0.9",
            "x-geo-city": "Raleigh, NC",
            "authorization": "Bearer secret",
            "cookie": "session=secret",
        },
    )

    assert response.status_code == 200

    gps_response = client.post(
        "/visit-metadata",
        json={
            "gps_consent": True,
            "gps_lat": 35.77959,
            "gps_lng": -78.63818,
        },
    )

    assert gps_response.status_code == 204

    with session_factory() as session:
        visit = session.scalar(select(VisitMetadata))

    assert visit is not None
    assert visit.tz == "America/New_York"
    assert float(visit.gps_lat) == pytest.approx(35.77959)
    assert float(visit.gps_lng) == pytest.approx(-78.63818)
    assert visit.consent is True
    assert visit.locality == "Raleigh, NC"
    assert visit.headers_json == {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/136.0.0.0 Safari/537.36",
        "referer": "https://www.payloadcat.ch/privacy",
        "accept-language": "en-US,en;q=0.9",
    }


def test_visit_metadata_rejects_partial_gps_payload() -> None:
    app, _ = _build_test_app(trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    bootstrap_response = client.get("/")

    assert bootstrap_response.status_code == 200

    response = client.post(
        "/visit-metadata",
        json={
            "gps_consent": True,
            "gps_lat": 35.77959,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": {
                "errors": [
                    {
                        "loc": ["body"],
                        "msg": "Value error, gps_lat and gps_lng must be provided together",
                        "type": "value_error",
                    }
                ],
            },
        },
        "request_id": response.headers["x-request-id"],
    }


def test_visit_metadata_ignores_gps_without_explicit_consent() -> None:
    app, session_factory = _build_test_app(trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    response = client.get(
        "/",
        headers={
            "x-geo-city": "Raleigh, NC",
        },
    )

    assert response.status_code == 200

    with session_factory() as session:
        visit = session.scalar(select(VisitMetadata))

    assert visit is not None
    assert visit.gps_lat is None
    assert visit.gps_lng is None
    assert visit.consent is False


def test_visit_metadata_update_requires_active_session_cookie() -> None:
    app, _ = _build_test_app(trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    response = client.post(
        "/visit-metadata",
        json={
            "gps_consent": True,
            "gps_lat": 35.77959,
            "gps_lng": -78.63818,
        },
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "inbox_not_found"


def test_visit_metadata_uses_independent_rate_limit_scope() -> None:
    app, session_factory = _build_test_app(rate_limit_per_minute=1, trusted_proxies=["testclient"])
    client = TestClient(app, base_url="https://testserver")

    bootstrap_response = client.get(
        "/",
        params={"timezone": "America/New_York"},
    )

    assert bootstrap_response.status_code == 200

    metadata_response = client.post(
        "/visit-metadata",
        json={
            "gps_consent": True,
            "gps_lat": 35.77959,
            "gps_lng": -78.63818,
        },
    )

    assert metadata_response.status_code == 204

    with session_factory() as session:
        visit = session.scalar(select(VisitMetadata))

    assert visit is not None
    assert float(visit.gps_lat) == pytest.approx(35.77959)
    assert float(visit.gps_lng) == pytest.approx(-78.63818)
    assert visit.consent is True


def test_visit_metadata_does_not_persist_gps_when_collection_is_disabled() -> None:
    app, session_factory = _build_test_app(trusted_proxies=["testclient"])
    overridden_settings = Settings(
        _env_file=None,
        trusted_proxies=["testclient"],
        gps_collection_enabled=False,
    )
    app.dependency_overrides[get_settings] = lambda: overridden_settings
    client = TestClient(app, base_url="https://testserver")

    bootstrap_response = client.get("/")

    assert bootstrap_response.status_code == 200

    metadata_response = client.post(
        "/visit-metadata",
        json={
            "gps_consent": True,
            "gps_lat": 35.77959,
            "gps_lng": -78.63818,
        },
    )

    assert metadata_response.status_code == 204

    with session_factory() as session:
        visit = session.scalar(select(VisitMetadata))

    assert visit is not None
    assert visit.gps_lat is None
    assert visit.gps_lng is None
    assert visit.consent is False


def test_openapi_includes_bootstrap_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/" in response.json()["paths"]


def test_get_root_returns_429_with_retry_hints_when_rate_limited() -> None:
    app, _ = _build_test_app(rate_limit_per_minute=1)
    client = TestClient(app, base_url="https://testserver")

    first_response = client.get("/", headers={"x-forwarded-for": "203.0.113.10"})
    second_response = client.get("/", headers={"x-forwarded-for": "203.0.113.10"})

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


def test_concurrent_revisit_with_same_session_cookie_keeps_active_inbox_stable() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = Path(temp_dir) / "bootstrap-concurrency.db"
        app, session_factory = _build_test_app(
            trusted_proxies=["testclient"],
            rate_limit_per_minute=100,
            database_url=f"sqlite+pysqlite:///{database_path.as_posix()}",
            use_static_pool=False,
        )

        with TestClient(app, base_url="https://testserver") as client:
            initial_response = client.get(
                "/",
                headers={"x-forwarded-for": "203.0.113.10"},
            )

        assert initial_response.status_code == 200
        cookie_header = initial_response.headers["set-cookie"].split(";", maxsplit=1)[0]
        initial_clsid = initial_response.json()["clsid"]

        def revisit(_: int) -> tuple[int, str]:
            with TestClient(app, base_url="https://testserver") as client:
                response = client.get(
                    "/",
                    headers={
                        "cookie": cookie_header,
                        "x-forwarded-for": "203.0.113.10",
                    },
                )
            return response.status_code, response.json()["clsid"]

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(revisit, range(4)))

        assert [status for status, _ in results] == [200, 200, 200, 200]
        assert {clsid for _, clsid in results} == {initial_clsid}

        with session_factory() as session:
            inbox_clsids = {
                row[0]
                for row in session.execute(select(VisitMetadata.inbox_id)).all()
            }
            inbox_count = session.query(VisitMetadata).count()

        assert len(inbox_clsids) == 1
        assert inbox_count == 5
        session_factory.kw["bind"].dispose()
