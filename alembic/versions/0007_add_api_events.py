"""add api_events table for analytics

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_events",
        sa.Column(
            "id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False
        ),
        sa.Column("ts", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("api_key_prefix", sa.Text(), nullable=True),
        sa.Column("query_string", sa.Text(), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Float(), nullable=False),
    )
    op.create_index("ix_api_events_ts", "api_events", ["ts"])
    op.create_index("ix_api_events_api_key_prefix", "api_events", ["api_key_prefix"])


def downgrade() -> None:
    op.drop_index("ix_api_events_api_key_prefix", table_name="api_events")
    op.drop_index("ix_api_events_ts", table_name="api_events")
    op.drop_table("api_events")
