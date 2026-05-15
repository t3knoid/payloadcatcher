from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.core.config import get_settings


def _build_alembic_config(database_url: str) -> Config:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_alembic_upgrade_and_downgrade_manage_initial_schema(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'alembic-test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    config = _build_alembic_config(database_url)

    command.upgrade(config, "head")

    engine = create_engine(database_url)
    inspector = inspect(engine)

    assert set(inspector.get_table_names()) >= {"alembic_version", "inboxes", "visit_metadata", "webhook_events"}
    assert {index["name"] for index in inspector.get_indexes("inboxes")} == {"ix_inboxes_expires_at"}
    assert {index["name"] for index in inspector.get_indexes("visit_metadata")} == {
        "ix_visit_metadata_inbox_id_visited_at"
    }
    assert {index["name"] for index in inspector.get_indexes("webhook_events")} == {
        "ix_webhook_events_inbox_id_dedup_key",
        "ix_webhook_events_inbox_id_received_at_desc",
        "ix_webhook_events_received_at",
    }

    command.downgrade(config, "base")

    downgraded_inspector = inspect(engine)
    assert downgraded_inspector.get_table_names() == ["alembic_version"]

    get_settings.cache_clear()