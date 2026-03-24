"""initial_schema

Revision ID: 0001
Revises:
Create Date: 2026-03-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("parent_code", sa.Text(), nullable=True),
        sa.Column("parent_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("code"),
    )

    op.create_table(
        "opportunities",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agency_code", sa.Text(), nullable=True),
        sa.Column("agency_name", sa.Text(), nullable=True),
        sa.Column("opportunity_number", sa.Text(), nullable=True),
        sa.Column("opportunity_status", sa.Text(), nullable=True),
        sa.Column("funding_instrument", sa.Text(), nullable=True),
        sa.Column("category", sa.Text(), nullable=True),
        sa.Column("cfda_numbers", sa.Text(), nullable=True),
        sa.Column("eligible_applicants", sa.Text(), nullable=True),
        sa.Column("post_date", sa.Text(), nullable=True),
        sa.Column("close_date", sa.Text(), nullable=True),
        sa.Column("last_updated", sa.Text(), nullable=True),
        sa.Column("award_floor", sa.Float(), nullable=True),
        sa.Column("award_ceiling", sa.Float(), nullable=True),
        sa.Column("estimated_total_funding", sa.Float(), nullable=True),
        sa.Column("expected_number_of_awards", sa.Integer(), nullable=True),
        sa.Column("cost_sharing_required", sa.Boolean(), nullable=True),
        sa.Column("contact_email", sa.Text(), nullable=True),
        sa.Column("contact_text", sa.Text(), nullable=True),
        sa.Column("additional_info_url", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_opportunities_source", "opportunities", ["source"])
    op.create_index("ix_opportunities_agency_code", "opportunities", ["agency_code"])
    op.create_index("ix_opportunities_opportunity_number", "opportunities", ["opportunity_number"])
    op.create_index("ix_opportunities_opportunity_status", "opportunities", ["opportunity_status"])
    op.create_index("ix_opportunities_post_date", "opportunities", ["post_date"])
    op.create_index("ix_opportunities_close_date", "opportunities", ["close_date"])

    op.create_table(
        "awards",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("award_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("agency_code", sa.Text(), nullable=True),
        sa.Column("agency_name", sa.Text(), nullable=True),
        sa.Column("cfda_numbers", sa.Text(), nullable=True),
        sa.Column("recipient_name", sa.Text(), nullable=True),
        sa.Column("recipient_uei", sa.Text(), nullable=True),
        sa.Column("award_amount", sa.Float(), nullable=True),
        sa.Column("total_funding", sa.Float(), nullable=True),
        sa.Column("award_date", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Text(), nullable=True),
        sa.Column("end_date", sa.Text(), nullable=True),
        sa.Column("place_state", sa.Text(), nullable=True),
        sa.Column("place_city", sa.Text(), nullable=True),
        sa.Column("place_country", sa.Text(), nullable=True),
        sa.Column("opportunity_number", sa.Text(), nullable=True),
        sa.Column("award_type", sa.Text(), nullable=True),
        sa.Column("raw_data", sa.Text(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_awards_source", "awards", ["source"])
    op.create_index("ix_awards_agency_code", "awards", ["agency_code"])
    op.create_index("ix_awards_cfda_numbers", "awards", ["cfda_numbers"])
    op.create_index("ix_awards_recipient_name", "awards", ["recipient_name"])
    op.create_index("ix_awards_opportunity_number", "awards", ["opportunity_number"])

    op.create_table(
        "ingestion_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("started_at", sa.Text(), nullable=False),
        sa.Column("completed_at", sa.Text(), nullable=True),
        sa.Column("records_processed", sa.Integer(), nullable=True),
        sa.Column("records_added", sa.Integer(), nullable=True),
        sa.Column("records_updated", sa.Integer(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_log")
    op.drop_index("ix_awards_opportunity_number", table_name="awards")
    op.drop_index("ix_awards_recipient_name", table_name="awards")
    op.drop_index("ix_awards_cfda_numbers", table_name="awards")
    op.drop_index("ix_awards_agency_code", table_name="awards")
    op.drop_index("ix_awards_source", table_name="awards")
    op.drop_table("awards")
    op.drop_index("ix_opportunities_close_date", table_name="opportunities")
    op.drop_index("ix_opportunities_post_date", table_name="opportunities")
    op.drop_index("ix_opportunities_opportunity_status", table_name="opportunities")
    op.drop_index("ix_opportunities_opportunity_number", table_name="opportunities")
    op.drop_index("ix_opportunities_agency_code", table_name="opportunities")
    op.drop_index("ix_opportunities_source", table_name="opportunities")
    op.drop_table("opportunities")
    op.drop_table("agencies")
