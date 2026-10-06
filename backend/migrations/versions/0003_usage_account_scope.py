"""Track credential-account boundaries without storing account IDs or tokens."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "api_calls",
        sa.Column("account_scope", sa.String(16), nullable=False, server_default="legacy"),
    )
    op.create_index("ix_api_calls_scope_created", "api_calls", ["account_scope", "created_at"])
    op.alter_column("api_calls", "account_scope", server_default=None)


def downgrade():
    op.drop_index("ix_api_calls_scope_created", table_name="api_calls")
    op.drop_column("api_calls", "account_scope")
