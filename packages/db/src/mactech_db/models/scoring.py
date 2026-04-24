from datetime import datetime
from typing import Any
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class CapabilityStatement(Base):
    __tablename__ = "capability_statements"
    __table_args__ = (
        UniqueConstraint("tenant_id", "title", name="uq_capability_tenant_title"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    related_naics: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    related_founders: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    artifact_s3_key: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    # `embedding vector(1024)` is added in the migration but not declared on
    # the ORM. Embedding ops use raw SQL via the embedding worker.


class OpportunityScore(Base):
    __tablename__ = "opportunity_scores"
    __table_args__ = (
        UniqueConstraint("tenant_id", "opportunity_id", name="uq_scores_tenant_opp"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
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
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_breakdown: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    assigned_founder_id: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("founders.id"), nullable=True
    )
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters_model: Mapped[str | None] = mapped_column(String, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
