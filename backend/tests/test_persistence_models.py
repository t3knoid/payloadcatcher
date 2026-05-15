from sqlalchemy import LargeBinary
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex

from app.persistence.base import Base
from app.persistence.models import WebhookEvent


def test_persistence_metadata_contains_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"inboxes", "visit_metadata", "webhook_events"}


def test_webhook_events_payload_storage_and_indexes_match_contract() -> None:
    table = WebhookEvent.__table__

    assert isinstance(table.c.payload_raw.type, LargeBinary)

    index_names = {index.name for index in table.indexes}
    assert index_names == {
        "ix_webhook_events_inbox_id_received_at_desc",
        "ix_webhook_events_received_at",
        "ix_webhook_events_inbox_id_dedup_key",
    }

    descending_index = next(
        index for index in table.indexes if index.name == "ix_webhook_events_inbox_id_received_at_desc"
    )
    compiled_index = str(CreateIndex(descending_index).compile(dialect=postgresql.dialect()))

    assert "received_at DESC" in compiled_index
