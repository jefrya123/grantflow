from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from grantflow.config import DATABASE_URL

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
    from grantflow.models import Base
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        # Create FTS5 virtual table if not exists
        conn.execute(text("""
            CREATE VIRTUAL TABLE IF NOT EXISTS opportunities_fts USING fts5(
                title, description, agency_name, category,
                content='opportunities',
                content_rowid='rowid'
            )
        """))
        conn.commit()
