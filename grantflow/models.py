from sqlalchemy import Column, Text, Float, Integer, Boolean, Index
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator, UserDefinedType
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime, timezone


class TSVECTORType(TypeDecorator):
    """PostgreSQL TSVECTOR that falls back to TEXT for other dialects (e.g. SQLite)."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import TSVECTOR
            return dialect.type_descriptor(TSVECTOR())
        return dialect.type_descriptor(Text())


class Base(DeclarativeBase):
    pass


class Opportunity(Base):
    __tablename__ = "opportunities"

    id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False, index=True)
    source_id = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    description = Column(Text)
    agency_code = Column(Text, index=True)
    agency_name = Column(Text)
    opportunity_number = Column(Text, index=True)
    opportunity_status = Column(Text, index=True)
    funding_instrument = Column(Text)
    category = Column(Text)
    cfda_numbers = Column(Text)
    eligible_applicants = Column(Text)  # JSON array
    post_date = Column(Text, index=True)
    close_date = Column(Text, index=True)
    last_updated = Column(Text)
    award_floor = Column(Float)
    award_ceiling = Column(Float)
    estimated_total_funding = Column(Float)
    expected_number_of_awards = Column(Integer)
    cost_sharing_required = Column(Boolean)
    contact_email = Column(Text)
    contact_text = Column(Text)
    additional_info_url = Column(Text)
    source_url = Column(Text)
    raw_data = Column(Text)
    created_at = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())
    updated_at = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())

    # Full-text search vector (PostgreSQL TSVECTOR; falls back to TEXT for SQLite)
    search_vector = Column(TSVECTORType, nullable=True)


class Award(Base):
    __tablename__ = "awards"

    id = Column(Text, primary_key=True)
    source = Column(Text, nullable=False, index=True)
    award_id = Column(Text, nullable=False)
    title = Column(Text)
    description = Column(Text)
    agency_code = Column(Text, index=True)
    agency_name = Column(Text)
    cfda_numbers = Column(Text, index=True)
    recipient_name = Column(Text, index=True)
    recipient_uei = Column(Text)
    award_amount = Column(Float)
    total_funding = Column(Float)
    award_date = Column(Text)
    start_date = Column(Text)
    end_date = Column(Text)
    place_state = Column(Text)
    place_city = Column(Text)
    place_country = Column(Text)
    opportunity_number = Column(Text, index=True)
    award_type = Column(Text)
    raw_data = Column(Text)
    created_at = Column(Text, default=lambda: datetime.now(timezone.utc).isoformat())


class Agency(Base):
    __tablename__ = "agencies"

    code = Column(Text, primary_key=True)
    name = Column(Text, nullable=False)
    parent_code = Column(Text)
    parent_name = Column(Text)


class IngestionLog(Base):
    __tablename__ = "ingestion_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(Text, nullable=False)
    started_at = Column(Text, nullable=False)
    completed_at = Column(Text)
    records_processed = Column(Integer, default=0)
    records_added = Column(Integer, default=0)
    records_updated = Column(Integer, default=0)
    status = Column(Text, default="running")
    error = Column(Text)
