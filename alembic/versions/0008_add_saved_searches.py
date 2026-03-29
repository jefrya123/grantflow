"""add_saved_searches

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-28

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, Sequence[str], None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("api_key_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=True),
        sa.Column("agency_code", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("eligible_applicants", sa.Text(), nullable=True),
        sa.Column("min_award", sa.Float(), nullable=True),
        sa.Column("max_award", sa.Float(), nullable=True),
        sa.Column("alert_email", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_alerted_at", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_saved_searches_api_key_id"),
        "saved_searches",
        ["api_key_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_saved_searches_is_active"),
        "saved_searches",
        ["is_active"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_saved_searches_is_active"), table_name="saved_searches")
    op.drop_index(op.f("ix_saved_searches_api_key_id"), table_name="saved_searches")
    op.drop_table("saved_searches")
