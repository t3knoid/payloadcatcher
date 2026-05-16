from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import create_app
from app.core.config import Settings, get_settings
from app.persistence.base import Base
from app.persistence.models import VisitMetadata
from app.persistence.session import get_db_session


def _build_test_app(*, trusted_proxies: list[str] | None = None) -> tuple[FastAPI, sessionmaker[Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    testing_session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    app = create_app()
    settings = Settings(_env_file=None, trusted_proxies=trusted_proxies or ["127.0.0.1", "::1"])

    def override_db_session() -> Generator[Session, None, None]:
        session = testing_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db_session] = override_db_session
    app.dependency_overrides[get_settings] = lambda: settings
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
    assert first_payload["callback_url"].endswith(f"/hook/{first_payload['clsid']}")
    assert first_payload["viewer_url"].endswith(f"/inbox/{first_payload['clsid']}")

    second_response = client.get("/")

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["new_session"] is False
    assert second_payload["clsid"] == first_payload["clsid"]
    assert second_payload["callback_url"] == first_payload["callback_url"]

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


def test_openapi_includes_bootstrap_route() -> None:
    app, _ = _build_test_app()
    client = TestClient(app)

    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/" in response.json()["paths"]