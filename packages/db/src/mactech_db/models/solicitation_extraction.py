"""Solicitation extraction — compliance + requirements matrices.

Section C of CaptureOS_Requirements.md. The extractor reads an
opportunity's description text (and, in V2, ingested attachments)
and uses Claude to produce two structured matrices that ProposalOS
will consume:

* Compliance matrix — every "shall" from Section L (instructions to
  offerors). Spine of the proposal.
* Requirements matrix — every technical / operational / security
  obligation from the SOW / PWS / CDRLs.

One ``SolicitationExtraction`` row per (tenant, opportunity), upserted
on regeneration. Items are children via ``extraction_id`` and are
deleted-and-recreated on every regen so the matrices always reflect
the latest extraction run.
"""

from datetime import datetime
from uuid import UUID

from decimal import Decimal

from sqlalchemy import (
    TIMESTAMP,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from mactech_db.base import Base


# Allowed extraction statuses. Persisted as String(16).
EXTRACTION_STATUSES = ("pending", "running", "complete", "failed")

# Allowed requirement categories. Persisted as String(32). Keep aligned with
# ``RequirementItem.category`` in the Capture Package schema.
REQUIREMENT_CATEGORIES = (
    "technical",
    "operational",
    "security",
    "staffing",
    "performance",
    "reporting",
    "other",
)


class SolicitationExtraction(Base):
    __tablename__ = "solicitation_extractions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "opportunity_id",
            name="uq_solicitation_extractions_tenant_opp",
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

    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'pending'")
    )
    source_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description_chars: Mapped[int | None] = mapped_column(Integer, nullable=True)

    compliance_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    requirements_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    evaluation_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Provenance + cost tracking — mirrors OpportunityBrief.
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(16), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ComplianceMatrixItem(Base):
    """A single 'shall' from Section L — one row per requirement.

    ``item_id`` is the stable, human-readable id within a single matrix
    (e.g., ``L-1``, ``L-3.2.a``). It's not globally unique; uniqueness is
    via the ``id`` UUID. ProposalOS uses ``item_id`` to map proposal
    sections to their compliance source.
    """

    __tablename__ = "compliance_matrix_items"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    extraction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
        nullable=False,
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

    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    section_l_citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pass_fail: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationPassFailItem(Base):
    """A pass/fail evaluation factor from Section M (or equivalent).

    The proposal must satisfy these or be eliminated from competition,
    independent of any scored evaluation.
    """

    __tablename__ = "evaluation_pass_fail_items"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    extraction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
        nullable=False,
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

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class EvaluationScoredFactor(Base):
    """A scored evaluation factor or sub-factor from Section M.

    ``weight`` is the relative weight as stated in Section M, when given;
    if Section M is qualitative ("most important", "approximately equal"),
    weight stays null and ``description`` carries the prose.
    """

    __tablename__ = "evaluation_scored_factors"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    extraction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
        nullable=False,
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

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )


class RequirementMatrixItem(Base):
    """A single technical / operational / security obligation from the
    SOW / PWS / CDRLs."""

    __tablename__ = "requirement_matrix_items"

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    extraction_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("solicitation_extractions.id", ondelete="CASCADE"),
        nullable=False,
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

    item_id: Mapped[str] = mapped_column(String(32), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    source_citation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default="other"
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=func.now()
    )
