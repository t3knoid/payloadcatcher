"""Create initial persistence schema.

Revision ID: 20260515_000001
Revises:
Create Date: 2026-05-15 00:00:01
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260515_000001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inboxes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("clsid", sa.String(length=36), nullable=False),
        sa.Column("source_ip", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_inboxes")),
        sa.UniqueConstraint("clsid", name=op.f("uq_inboxes_clsid")),
    )
    op.create_index("ix_inboxes_expires_at", "inboxes", ["expires_at"], unique=False)

    op.create_table(
        "visit_metadata",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inbox_id", sa.Uuid(), nullable=False),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_ip", sa.Text(), nullable=False),
        sa.Column("referer_url", sa.Text(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("browser", sa.Text(), nullable=True),
        sa.Column("device", sa.Text(), nullable=True),
        sa.Column("lang", sa.Text(), nullable=True),
        sa.Column("tz", sa.Text(), nullable=True),
        sa.Column("locality", sa.Text(), nullable=True),
        sa.Column("headers_json", sa.JSON(), nullable=False),
        sa.Column("gps_lat", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("gps_lng", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("consent", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["inbox_id"], ["inboxes.id"], name=op.f("fk_visit_metadata_inbox_id_inboxes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_visit_metadata")),
    )
    op.create_index(
        "ix_visit_metadata_inbox_id_visited_at",
        "visit_metadata",
        ["inbox_id", "visited_at"],
        unique=False,
    )

    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("inbox_id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("headers_json", sa.JSON(), nullable=False),
        sa.Column("payload_raw", sa.LargeBinary(), nullable=False),
        sa.Column("payload_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("payload_encoding", sa.Text(), nullable=True),
        sa.Column("payload_yaml", sa.Text(), nullable=False),
        sa.Column("source_ip", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.ForeignKeyConstraint(["inbox_id"], ["inboxes.id"], name=op.f("fk_webhook_events_inbox_id_inboxes"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_events")),
        sa.UniqueConstraint("request_id", name=op.f("uq_webhook_events_request_id")),
    )
    op.create_index(
        "ix_webhook_events_inbox_id_received_at_desc",
        "webhook_events",
        ["inbox_id", sa.text("received_at DESC")],
        unique=False,
    )
    op.create_index("ix_webhook_events_received_at", "webhook_events", ["received_at"], unique=False)
    op.create_index(
        "ix_webhook_events_inbox_id_dedup_key",
        "webhook_events",
        ["inbox_id", "dedup_key"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_webhook_events_inbox_id_dedup_key", table_name="webhook_events")
    op.drop_index("ix_webhook_events_received_at", table_name="webhook_events")
    op.drop_index("ix_webhook_events_inbox_id_received_at_desc", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("ix_visit_metadata_inbox_id_visited_at", table_name="visit_metadata")
    op.drop_table("visit_metadata")

    op.drop_index("ix_inboxes_expires_at", table_name="inboxes")
    op.drop_table("inboxes")