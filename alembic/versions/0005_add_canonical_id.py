"""add_canonical_id

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add canonical_id column and index to opportunities table."""
    op.add_column('opportunities', sa.Column('canonical_id', sa.Text(), nullable=True))
    op.create_index('ix_opportunities_canonical_id', 'opportunities', ['canonical_id'])


def downgrade() -> None:
    """Remove canonical_id column and index from opportunities table."""
    op.drop_index('ix_opportunities_canonical_id', table_name='opportunities')
    op.drop_column('opportunities', 'canonical_id')
