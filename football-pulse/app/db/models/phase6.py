"""FootballPulse-owned publication deliveries (additive).

One row per publish intent: deterministic idempotency_key over
(pulse, package/content identity, platform, account, version). Repeats reuse
the row; retries after transient failure keep the same intent; a genuinely
new version mints a new key. Remote receipts prove real publication.
"""
from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.models import _now, _uuid


class PublicationDelivery(Base):
    __tablename__ = "publication_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=_uuid)
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    package_ref: Mapped[str] = mapped_column(String(128), default="", index=True)
    platform: Mapped[str] = mapped_column(String(32), default="webhook", index=True)
    target_account: Mapped[str] = mapped_column(String(128), default="")
    content_version: Mapped[str] = mapped_column(String(32), default="v1")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    remote_id: Mapped[str] = mapped_column(String(256), default="")
    remote_status: Mapped[str] = mapped_column(String(32), default="")
    last_error: Mapped[str] = mapped_column(Text, default="")
    scheduled_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), default=_now)
    published_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
