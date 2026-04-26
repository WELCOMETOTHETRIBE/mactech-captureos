from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


class Founder(Base):
    __tablename__ = "founders"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_founders_tenant_slug"),
    )

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Slug is unique within a tenant (composite UQ above), not globally.
    slug: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    pillar: Mapped[str] = mapped_column(String, nullable=False)
    bio: Mapped[str | None] = mapped_column(String, nullable=True)
    areas_of_expertise: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    digest_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class FounderNaicsMatrix(Base):
    __tablename__ = "founder_naics_matrix"

    founder_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), ForeignKey("founders.id"), primary_key=True
    )
    naics_code: Mapped[str] = mapped_column(
        String, ForeignKey("naics_codes.code"), primary_key=True, index=True
    )
    affinity: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
