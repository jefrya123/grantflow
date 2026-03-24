"""add topic_tags column to opportunities

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('opportunities', sa.Column('topic_tags', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('opportunities', 'topic_tags')
