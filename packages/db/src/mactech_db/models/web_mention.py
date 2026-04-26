"""SerpAPI per-opportunity cache.

Sprint 19. One row per (tenant, opportunity, query_kind). The kinds
align with the ones the API queries on opp-detail load:
program-name, incumbent, agency-news. 7-day TTL enforced at read time.
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


WEB_MENTION_KINDS = ("program", "incumbent", "agency_news")


class WebMentionCache(Base):
    __tablename__ = "web_mention_cache"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "opportunity_id",
            "query_kind",
            name="uq_web_mention_cache_tenant_opp_kind",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    opportunity_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
        nullable=False,
    )
    query_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    results: Mapped[list[dict]] = mapped_column(JSONB, nullable=False)
    result_count: Mapped[int] = mapped_column(Integer, nullable=False)
    engine: Mapped[str] = mapped_column(
        String(32), nullable=False, default="google"
    )
    fetched_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
