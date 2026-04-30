from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import TIMESTAMP, ForeignKey, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class SavedSearch(Base):
    __tablename__ = "saved_searches"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    owner_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("founders.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    alert_threshold: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("70"))
    alert_cadence: Mapped[str] = mapped_column(String, nullable=False, server_default=text("'daily'"))
    alert_channels: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[\"email\"]'::jsonb")
    )
    last_delivered_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
