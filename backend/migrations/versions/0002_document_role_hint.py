"""Preserve manual hints separately from AI-assigned document types."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("documents", sa.Column("role_hint", sa.String(), nullable=True))
    op.execute("UPDATE documents SET role_hint = role")


def downgrade():
    op.drop_column("documents", "role_hint")
