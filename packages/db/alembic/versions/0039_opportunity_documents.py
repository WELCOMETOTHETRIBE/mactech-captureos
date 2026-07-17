"""Per-document acquisition + provenance.

Revision ID: 0039_opportunity_documents
Revises: 0038_ingestion_metrics

Slice 2 of the capture-engine overhaul. Attachments were a single concatenated
``opportunities_raw.attachment_text`` blob with no provenance. This adds
per-document rows (keyed by content hash for reprocess-on-change) and
page/section rows that become the stable evidence anchors, plus a
package-completeness summary on the notice.

Both new tables are SHARED (no ``tenant_id``) — the procurement package belongs
to the notice, not a tenant — mirroring ``opportunities_enriched``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0039_opportunity_documents"
down_revision: str | Sequence[str] | None = "0038_ingestion_metrics"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_documents",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_url", sa.String(2048), nullable=True),
        sa.Column("filename", sa.String(512), nullable=True),
        sa.Column("doc_class", sa.String(48), nullable=False, server_default=sa.text("'other'")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(1024), nullable=True),
        sa.Column("mime_type", sa.String(128), nullable=True),
        sa.Column("doc_format", sa.String(16), nullable=True),
        sa.Column("byte_size", sa.BigInteger, nullable=True),
        sa.Column("page_count", sa.Integer, nullable=True),
        sa.Column("extracted_char_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("ocr_used", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("archived_from", sa.String(1024), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default=sa.text("'not_discovered'")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("fetched_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("reprocessed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("opportunity_id", "content_hash", name="uq_opportunity_documents_opp_hash"),
    )
    op.create_index(
        "ix_opportunity_documents_opp", "opportunity_documents", ["opportunity_id"]
    )

    op.create_table(
        "document_sections",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunity_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "opportunity_id",
            UUID(as_uuid=True),
            sa.ForeignKey("opportunities_raw.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer, nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("section_heading", sa.String(255), nullable=True),
        sa.Column("section_path", sa.String(255), nullable=True),
        sa.Column("char_start", sa.Integer, nullable=False, server_default="0"),
        sa.Column("char_end", sa.Integer, nullable=False, server_default="0"),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_document_sections_document", "document_sections", ["document_id"]
    )
    op.create_index(
        "ix_document_sections_opp", "document_sections", ["opportunity_id"]
    )

    op.add_column(
        "opportunities_raw",
        sa.Column("documents_status", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("opportunities_raw", "documents_status")
    op.drop_index("ix_document_sections_opp", table_name="document_sections")
    op.drop_index("ix_document_sections_document", table_name="document_sections")
    op.drop_table("document_sections")
    op.drop_index("ix_opportunity_documents_opp", table_name="opportunity_documents")
    op.drop_table("opportunity_documents")
