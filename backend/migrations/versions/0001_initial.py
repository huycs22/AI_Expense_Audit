"""Initial feature tables. Snapshot of v1 metadata; future changes need new revisions."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "audits",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("assessment", sa.String(), nullable=False),
        sa.Column("current_stage", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("report", JSONB, nullable=False),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("audit_id", sa.String(32), sa.ForeignKey("audits.id"), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("extraction", JSONB),
    )
    op.create_table(
        "document_files",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("media_type", sa.String(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_table(
        "document_pages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id"), nullable=False),
        sa.Column("file_id", sa.String(32), sa.ForeignKey("document_files.id"), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("evidence", JSONB, nullable=False),
        sa.Column("image_path", sa.String(), nullable=False),
    )
    op.create_table(
        "stage_runs",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("audit_id", sa.String(32), sa.ForeignKey("audits.id"), nullable=False),
        sa.Column("document_id", sa.String(32), sa.ForeignKey("documents.id")),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("prompt_hash", sa.String()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("error", sa.Text()),
    )
    op.create_table(
        "audit_findings",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("audit_id", sa.String(32), sa.ForeignKey("audits.id"), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
    )
    op.create_table(
        "api_calls",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("audit_id", sa.String(32), sa.ForeignKey("audits.id")),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("prompt_tokens", sa.Integer()),
        sa.Column("completion_tokens", sa.Integer()),
        sa.Column("estimated_neurons", sa.Float()),
        sa.Column("estimated_usd", sa.Float()),
        sa.Column("reserved_neurons", sa.Float(), nullable=False),
        sa.Column("pricing_version", sa.String(), nullable=False),
        sa.Column("usage", JSONB),
        sa.Column("error_code", sa.String()),
    )
    for table, column in [
        ("documents", "audit_id"),
        ("document_files", "document_id"),
        ("document_pages", "document_id"),
        ("stage_runs", "audit_id"),
        ("audit_findings", "audit_id"),
        ("api_calls", "audit_id"),
    ]:
        op.create_index(f"ix_{table}_{column}", table, [column])


def downgrade():
    for table in [
        "api_calls",
        "audit_findings",
        "stage_runs",
        "document_pages",
        "document_files",
        "documents",
        "audits",
    ]:
        op.drop_table(table)
