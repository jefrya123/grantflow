# Deferred Items

## FTS5 references in ingest files (out of scope for 01-02)

Found during Plan 01-02 execution. These files still reference the SQLite FTS5
virtual table (`opportunities_fts`) and will need updating in Phase 2 when the
ingest pipeline is migrated to PostgreSQL:

- `grantflow/ingest/grants_gov.py` — DELETE + INSERT into `opportunities_fts`
- `grantflow/ingest/run_all.py` — DELETE + INSERT into `opportunities_fts`

These are ingest-layer concerns, not route/model concerns. Plan 01-02 scope was
limited to models.py, api/routes.py, web/routes.py, and the Alembic migration.
