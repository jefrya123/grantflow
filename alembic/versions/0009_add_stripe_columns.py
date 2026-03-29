"""add_stripe_columns

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-29

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, Sequence[str], None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("api_keys", sa.Column("stripe_customer_id", sa.Text(), nullable=True))
    op.add_column(
        "api_keys", sa.Column("stripe_subscription_id", sa.Text(), nullable=True)
    )
    op.add_column("api_keys", sa.Column("plaintext_key_once", sa.Text(), nullable=True))
    op.create_index(
        "ix_api_keys_stripe_subscription_id",
        "api_keys",
        ["stripe_subscription_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_api_keys_stripe_subscription_id", table_name="api_keys")
    op.drop_column("api_keys", "plaintext_key_once")
    op.drop_column("api_keys", "stripe_subscription_id")
    op.drop_column("api_keys", "stripe_customer_id")
