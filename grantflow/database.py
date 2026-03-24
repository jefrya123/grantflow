from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from grantflow.config import DATABASE_URL

# Determine dialect
_is_postgres = DATABASE_URL.startswith("postgresql") or DATABASE_URL.startswith("postgres")

if _is_postgres:
    # PostgreSQL: use psycopg2 for sync ORM (asyncpg is for async; routes stay sync for now)
    # Replace postgres:// with postgresql+psycopg2:// for SQLAlchemy sync engine
    _sync_url = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    if "postgresql://" in _sync_url and "+psycopg2" not in _sync_url:
        _sync_url = _sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)
    engine = create_engine(_sync_url, echo=False, pool_pre_ping=True)
else:
    # SQLite: keep original setup with pragmas
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create tables if they do not exist. For PostgreSQL, prefer 'alembic upgrade head'."""
    from grantflow.models import Base
    Base.metadata.create_all(bind=engine)
