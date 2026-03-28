"""add tsvector full-text search

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Add the tsvector column
    op.add_column(
        "opportunities",
        sa.Column("search_vector", postgresql.TSVECTOR(), nullable=True),
    )

    # Create GIN index for fast FTS queries
    op.create_index(
        "ix_opportunities_search_vector",
        "opportunities",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Create trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION opportunities_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.search_vector := to_tsvector(
                'english',
                COALESCE(NEW.title, '') || ' ' ||
                COALESCE(NEW.description, '') || ' ' ||
                COALESCE(NEW.agency_name, '') || ' ' ||
                COALESCE(NEW.category, '')
            );
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Attach trigger to fire on insert and update
    op.execute("""
        CREATE TRIGGER opportunities_search_vector_trigger
        BEFORE INSERT OR UPDATE ON opportunities
        FOR EACH ROW
        EXECUTE FUNCTION opportunities_search_vector_update();
    """)

    # Backfill existing rows
    op.execute("""
        UPDATE opportunities
        SET search_vector = to_tsvector(
            'english',
            COALESCE(title, '') || ' ' ||
            COALESCE(description, '') || ' ' ||
            COALESCE(agency_name, '') || ' ' ||
            COALESCE(category, '')
        )
        WHERE search_vector IS NULL;
    """)


def downgrade():
    op.execute(
        "DROP TRIGGER IF EXISTS opportunities_search_vector_trigger ON opportunities"
    )
    op.execute("DROP FUNCTION IF EXISTS opportunities_search_vector_update()")
    op.drop_index("ix_opportunities_search_vector", table_name="opportunities")
    op.drop_column("opportunities", "search_vector")
