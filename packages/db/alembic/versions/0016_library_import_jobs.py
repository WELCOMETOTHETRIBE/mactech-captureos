"""library_import_jobs — async OCR + extraction queue

Revision ID: 0016_library_import_jobs
Revises: 0015_founder_tenant_scope
Create Date: 2026-04-26

Phase 3 sprint 18. PyMuPDF text extraction is fast and stays inline,
but OCR fall-through (Tesseract on a rasterized 12-page scan) can hit
60-180s — too long for an HTTP request. This table queues the OCR +
LLM-extraction work so the API endpoint can hand it off and return
202 Accepted.

  kind         past_performance | capability_statement
  status       queued | running | done | failed
  file_blob    20 MB cap (matches API enforcement)
  result_id    set on success — points to past_performance.id or
               capability_statements.id depending on kind
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0016_library_import_jobs"
down_revision: str | Sequence[str] | None = "0015_founder_tenant_scope"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "library_import_jobs",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column(
            "tenant_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_founder_id",
            UUID(as_uuid=True),
            sa.ForeignKey("founders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("file_blob", sa.LargeBinary(), nullable=False),
        sa.Column("text_chars", sa.Integer(), nullable=True),
        sa.Column("result_id", UUID(as_uuid=True), nullable=True),
        sa.Column("notes", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "kind in ('past_performance','capability_statement')",
            name="ck_library_import_jobs_kind",
        ),
        sa.CheckConstraint(
            "status in ('queued','running','done','failed')",
            name="ck_library_import_jobs_status",
        ),
    )
    op.create_index(
        "ix_library_import_jobs_tenant_status",
        "library_import_jobs",
        ["tenant_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_library_import_jobs_tenant_status",
        table_name="library_import_jobs",
    )
    op.drop_table("library_import_jobs")
