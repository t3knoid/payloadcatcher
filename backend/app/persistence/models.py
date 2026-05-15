from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, JSON, LargeBinary, Numeric, String, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.persistence.base import Base


class Inbox(Base):
    __tablename__ = "inboxes"
    __table_args__ = (
        Index("ix_inboxes_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    clsid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    source_ip: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class VisitMetadata(Base):
    __tablename__ = "visit_metadata"
    __table_args__ = (
        Index("ix_visit_metadata_inbox_id_visited_at", "inbox_id", "visited_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("inboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    visited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_ip: Mapped[str] = mapped_column(Text, nullable=False)
    referer_url: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
    browser: Mapped[str | None] = mapped_column(Text)
    device: Mapped[str | None] = mapped_column(Text)
    lang: Mapped[str | None] = mapped_column(Text)
    tz: Mapped[str | None] = mapped_column(Text)
    locality: Mapped[str | None] = mapped_column(Text)
    headers_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    gps_lat: Mapped[float | None] = mapped_column(Numeric(9, 6))
    gps_lng: Mapped[float | None] = mapped_column(Numeric(9, 6))
    consent: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("0"))


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (
        Index("ix_webhook_events_inbox_id_received_at_desc", "inbox_id", text("received_at DESC")),
        Index("ix_webhook_events_received_at", "received_at"),
        Index("ix_webhook_events_inbox_id_dedup_key", "inbox_id", "dedup_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(), primary_key=True, default=uuid.uuid4)
    inbox_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(),
        ForeignKey("inboxes.id", ondelete="CASCADE"),
        nullable=False,
    )
    request_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    headers_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
    payload_raw: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    payload_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload_encoding: Mapped[str | None] = mapped_column(Text)
    payload_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    source_ip: Mapped[str] = mapped_column(Text, nullable=False)
    dedup_key: Mapped[str | None] = mapped_column(Text)
    is_duplicate: Mapped[bool] = mapped_column(nullable=False, default=False, server_default=text("0"))