# Architecture Patterns: Government Grants DaaS Platform

**Domain:** Data-as-a-Service, government data aggregation, multi-source ETL pipeline
**Researched:** 2026-03-24
**Confidence:** HIGH (current architecture verified from codebase; patterns from multiple corroborated sources)

---

## Current Architecture Assessment

The existing system is a **monolithic FastAPI app** with SQLite. It works but has structural problems that block the next stage of growth:

- No automated pipeline scheduling — data goes stale at deploy
- Single-file ingestion runs all sources sequentially with no retry or failure isolation
- SQLite serializes all writes, blocking reads during large ingestion runs (~81K rows from Grants.gov)
- No monitoring surface — operators can't see pipeline health without querying DB directly
- FTS rebuilt manually after full-run only — external-content FTS5 stays stale if anything else writes to the table
- No API key layer — open access, CORS wildcard, no rate limiting

The good news: the monolith is the right starting point. The architecture evolution is additive — not a rewrite.

---

## Recommended Target Architecture

### Mental Model: Three Separated Concerns

```
[Acquisition Layer]  →  [Storage + Quality Layer]  →  [Delivery Layer]
  Scrapers / APIs         PostgreSQL + Normalization      FastAPI + Cache
  Prefect orchestration   Data quality checks             Rate limiting + keys
  Source adapters         FTS index maintenance           Search + detail API
```

These three layers have very different operational profiles:
- Acquisition: runs on a schedule, is I/O bound, fails often, needs retry logic
- Storage: read-heavy API traffic + nightly heavy writes, needs to handle both
- Delivery: latency-sensitive, needs to be fast and observable

They should be deployable independently but can run on the same single VPS initially.

---

## Component Boundaries

### Component 1: Source Adapters (`grantflow/ingest/sources/`)

**Responsibility:** One module per external source. Download, parse, yield normalized dicts.

**Boundary:** Each adapter is a pure function — takes config, returns an iterator of normalized records. No DB access inside adapters.

```
grants_gov.py     → yields Opportunity dicts
sam_gov.py        → yields Opportunity dicts (contracts)
sbir.py           → yields Award + Opportunity dicts
usaspending.py    → yields Award dicts
state_*.py        → yields Opportunity dicts (one file per state)
```

**Communicates with:** Pipeline Orchestrator (called by), Storage Layer (does not touch directly)

**Why separate:** Adapters for state portals will use Scrapling (anti-bot bypass). Mixing scraping logic with DB logic makes both harder to test and retry. Isolated adapters can be tested against fixtures without a database.

### Component 2: Pipeline Orchestrator (`grantflow/pipeline/`)

**Responsibility:** Schedule and coordinate adapter execution. Handle retries, failures, and run logging. Call the normalizer/deduplication layer after acquisition.

**Technology:** Prefect (self-hosted, open source). Rationale:
- Pure Python decorators — no DSL or YAML config
- Built-in retry, caching, scheduling, and failure alerts
- Self-hosted Prefect server is a lightweight SQLite/PostgreSQL-backed process
- Supports cron schedules out of the box
- Lower operational overhead than Airflow for a solo operator
- No Kubernetes requirement

**Boundary:** Orchestrator knows about adapters and the storage write interface. It does not know about the API layer.

**Communicates with:** Source Adapters (calls), Storage Layer (passes normalized records to), Monitoring (emits run results to)

**Run model:**
```
Daily cron (00:00 UTC)
  → run_federal_sources()      [Grants.gov, SAM.gov, USAspending, SBIR]
  → run_state_sources()        [top-10 state scrapers, parallelizable]
  → run_normalization_pass()   [dedup, status derivation, FTS rebuild]
  → emit_pipeline_metrics()    [record counts, error summary, freshness timestamp]
```

### Component 3: Normalization + Quality Layer (`grantflow/quality/`)

**Responsibility:** Deduplication, status derivation, date normalization, cross-source entity resolution.

**Boundary:** Operates on records already in the database (post-ingest pass). Read-modify-write pattern. Does not fetch from external sources.

**Key functions:**
- **Deduplication:** Identify duplicate opportunities across sources (same grant listed on Grants.gov and state portal). Use `opportunity_number` as primary key; fall back to fuzzy title + agency + deadline match for state sources without canonical IDs.
- **Status derivation:** Compute `opportunity_status` from `close_date` vs. today for sources that don't provide explicit status (SBIR, state sources).
- **Date normalization:** Centralize all `_normalize_date()` / `_parse_date()` logic into one shared utility. Currently fragmented across three ingest files with different format coverage.
- **FTS rebuild trigger:** Rebuild FTS index once after all normalization passes complete — never mid-ingest.

**Communicates with:** Storage Layer (read/write), Pipeline Orchestrator (called by)

### Component 4: Storage Layer (`grantflow/database.py` + models)

**Technology decision: Migrate from SQLite to PostgreSQL.**

Rationale:
- SQLite WAL mode is fine for single-process reads, but nightly ingestion of 100K+ rows blocks concurrent reads during flush
- PostgreSQL `tsvector` + GIN index replaces SQLite FTS5 — better ranking, better multi-column weighting, no external-content staleness issue
- PostgreSQL supports `INSERT ... ON CONFLICT DO UPDATE` (upsert) natively — solves the N+1 SELECT-then-INSERT pattern currently in all three ingesters
- SQLAlchemy models are already compatible — only `DATABASE_URL` and FTS query construction change
- Alembic handles schema migrations going forward

**Migration path:** SQLAlchemy ORM abstracts the engine. Add Alembic, swap `DATABASE_URL`, replace raw FTS5 SQL with `tsvector` queries. One sprint, low risk.

**Boundary:** Owns all persistent state. Exposes session factory and schema to all other components.

**Communicates with:** Normalization Layer (write), API Layer (read), Orchestrator (write via ingest)

**Schema additions needed:**
- `sources` table: registry of configured scrapers with last_run, last_success, record_count
- `pipeline_runs` table: replaces/extends `IngestionLog` with per-run telemetry
- `data_quality_flags` table: records detected anomalies (schema change, volume drop, dedup conflicts)
- `api_keys` table: hashed keys, tier, rate limit config, usage counters

### Component 5: API Layer (`grantflow/api/`)

**Responsibility:** Serve clean, versioned, rate-limited JSON API.

**Technology:** FastAPI (keep existing). Add:
- `slowapi` or custom Redis-backed middleware for rate limiting
- API key authentication via `X-API-Key` header (validated against `api_keys` table)
- Pydantic v2 response models (`OpportunityResponse`, `AwardResponse`) — eliminates the fragile `_opportunity_to_dict()` hand-roller
- Shared `build_opportunity_query()` helper in `grantflow/queries.py` — eliminates duplicated search logic between API and web routes
- `/api/v1/status` endpoint: exposes last pipeline run, freshness timestamp, record counts

**Boundary:** Read-only against storage. No writes except API key usage counter increments. Does not know about pipeline or scraper internals.

**Communicates with:** Storage Layer (read), Cache Layer (optional, read-through)

**API versioning:** `/api/v1/` prefix is already in place. Keep it. Add `Deprecation` headers if v2 is ever introduced.

### Component 6: Search + Web UI (`grantflow/web/`)

**Responsibility:** Server-rendered search interface for direct users.

**Boundary:** Calls the same `build_opportunity_query()` helper as the API layer — no more duplicated logic. Thin layer over the shared query builder.

**Communicates with:** Storage Layer (via shared query helper)

### Component 7: Monitoring Surface

**Responsibility:** Expose pipeline health to the operator. Alert on failures.

**Implementation (minimal, solo operator appropriate):**
- `/api/v1/status` endpoint in the API layer — last run time, source-by-source record counts, any errors
- Pipeline run results written to `pipeline_runs` table by orchestrator
- Simple anomaly rules checked post-ingestion: volume drop >20% from previous run = alert
- Email/Slack alert on pipeline failure via Prefect's built-in notification hooks
- **No separate observability stack needed** (Prometheus/Grafana is overkill for a solo VPS)

**Communicates with:** Pipeline Orchestrator (receives run telemetry), API Layer (surfaces telemetry to callers)

---

## Data Flow

### Nightly Ingestion Flow

```
[Prefect Scheduler]
        |
        ├── [Federal Source Adapters] ────────────────────────────┐
        │     grants_gov.py → parse XML bulk extract               │
        │     sam_gov.py    → paginate contracts API               │
        │     sbir.py       → download + parse CSV                 │
        │     usaspending.py→ paginate awards API                  │
        │                                                           ▼
        └── [State Source Adapters] ──────────────────────► [Normalization Layer]
              state_ca.py  → Scrapling + parse HTML                │
              state_tx.py  → ...                                    │  dedup
              ...                                                   │  status derivation
                                                                    │  date normalization
                                                                    ▼
                                                           [PostgreSQL]
                                                                    │
                                                                    ▼
                                                         [FTS tsvector rebuild]
                                                                    │
                                                                    ▼
                                                         [pipeline_runs record written]
                                                                    │
                                                                    ▼
                                                         [Anomaly check → alert if fail]
```

### API Request Flow

```
[External caller]
        |
        ▼
[FastAPI /api/v1/opportunities/search]
        |
        ├── API key validation (api_keys table)
        ├── Rate limit check (sliding window, per-key)
        │
        ▼
[build_opportunity_query(db, filters)]
        |
        ├── FTS tsvector query (if q= param)
        ├── Filter clauses (status, agency, closing_before, etc.)
        ├── Pagination
        │
        ▼
[PostgreSQL]
        |
        ▼
[OpportunityResponse Pydantic model serialization]
        |
        ▼
[JSON response]
```

### State Data Scraping Flow

```
[Prefect Task: scrape_state(state_code)]
        |
        ├── Scrapling adapter fetches portal page (anti-bot bypass)
        ├── Parses grant listings with source-specific CSS selectors
        ├── Yields normalized dicts conforming to Opportunity schema
        ├── On 4xx/5xx: Prefect retries with exponential backoff (max 3)
        ├── On parse failure: log to pipeline_runs, skip record, continue
        │
        ▼
[Normalization Layer]
        |
        ├── Check for duplicate against federal sources (opportunity_number match)
        ├── Derive status from close_date
        ├── Store with source="state_{code}"
        │
        ▼
[PostgreSQL upsert on conflict(id)]
```

---

## Suggested Build Order

Component dependencies create a natural build sequence:

### Phase 1 — Foundation (enables everything else)
1. **PostgreSQL migration** — swap DATABASE_URL, add Alembic, migrate FTS to tsvector
   - Unblocks: concurrent reads during ingest, native upsert, better FTS
   - Risk: low (SQLAlchemy abstracts the engine)
2. **Shared query builder** (`grantflow/queries.py`) — extract duplicated search logic
   - Unblocks: adding new filters once instead of twice, testing search logic
3. **Pydantic response models** — replace `_opportunity_to_dict()`
   - Unblocks: reliable API responses as new fields are added

### Phase 2 — Pipeline Hardening (enables reliable daily data)
4. **Prefect orchestration** — add `@flow` and `@task` decorators to ingest functions
   - Unblocks: scheduled daily runs, retry on failure, failure alerts
5. **Source adapter isolation** — move DB writes out of adapter functions
   - Unblocks: unit testing adapters with fixtures, cleaner retry behavior
6. **Normalization pass** — centralize date normalization, status derivation, post-ingest dedup
   - Unblocks: data quality sufficient to charge for

### Phase 3 — API Layer (enables monetization)
7. **API key table + middleware** — hashed keys, tier config, usage tracking
   - Unblocks: issuing keys to paying customers
8. **Rate limiting** — slowapi or custom Redis sliding window per key
   - Unblocks: tiered pricing (free = 100 req/day, paid = unlimited)
9. **`/api/v1/status` endpoint** — pipeline health surface
   - Unblocks: customer trust, self-service debugging

### Phase 4 — Data Expansion (builds the moat)
10. **SAM.gov contracts adapter** — federal contract opportunities
11. **State source adapters** — top 10 states using Scrapling
12. **Cross-source award linkage** — normalize CFDA numbers into linking table, replace `ilike` scan

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Microservices Too Early

**What it looks like:** Separate Docker containers for scraper, API, pipeline scheduler, before there is revenue.

**Why bad:** Operational overhead for one person is severe. Networking, service discovery, shared secrets, container orchestration — all become maintenance burden before the product is proven.

**Instead:** Single VPS, single Python process for the API, Prefect as a subprocess or second lightweight process. Split into services only if a specific bottleneck demands it.

### Anti-Pattern 2: Message Queue Before Proving Need

**What it looks like:** Adding Kafka or RabbitMQ between scraper and storage to "scale."

**Why bad:** Daily batch ingest at 100K records does not need a message queue. A queue adds infrastructure to maintain, introduces failure modes, and requires more operational expertise. Prefect task flows handle retry, ordering, and failure isolation without a broker.

**Instead:** Prefect task DAG with retry policies. Add a queue if throughput exceeds what synchronous task execution can handle — that threshold is far above where this product will be for months.

### Anti-Pattern 3: Rebuilding FTS Mid-Ingest

**What it looks like:** Each source adapter rebuilds the FTS index when it finishes (current behavior in `grants_gov.py`).

**Why bad:** With PostgreSQL `tsvector`, intermediate rebuilds are expensive and wasteful. With the existing SQLite FTS5 external-content table, rebuilding mid-ingest leaves the index in an inconsistent state for the remainder of the run.

**Instead:** One FTS rebuild/refresh at the end of all normalization passes. PostgreSQL triggers can maintain `tsvector` columns automatically on insert/update, eliminating manual rebuild entirely.

### Anti-Pattern 4: Storing Raw HTML in the Main DB

**What it looks like:** For state scrapers, storing full HTML of scraped pages alongside normalized records in the `opportunities` table.

**Why bad:** HTML content is 50-500x the size of normalized data. It bloats the primary table, slows all queries, and the raw HTML is only useful for re-parsing — a separate concern.

**Instead:** Store raw HTML to a separate `raw_scrapes` table (or flat files with date-based paths) keyed by `(source, source_id, scraped_at)`. Keep the main table normalized and lean.

### Anti-Pattern 5: API Keys in Plaintext

**What it looks like:** Storing issued API keys as plain strings in the database.

**Why bad:** If the database is compromised, all customer keys are immediately usable.

**Instead:** Store `SHA-256(key)` in the `api_keys` table. Issue the plaintext key to the customer exactly once at creation. Validate incoming `X-API-Key` headers by hashing and comparing.

---

## Scalability Considerations

| Concern | Single VPS (current) | 10K req/day | 100K req/day |
|---------|---------------------|-------------|--------------|
| Database | PostgreSQL on VPS | Same, add pgBouncer connection pooler | Read replica for API queries |
| Search | tsvector + GIN index | Same | Same (GIN handles millions of rows) |
| Ingest | Sequential Prefect tasks | Same | Parallelize state scrapers as concurrent tasks |
| API | Single uvicorn process | Multiple uvicorn workers (gunicorn) | Same, or add nginx load balancer |
| Rate limiting | In-process (no Redis) | Redis for distributed limits | Same |
| State scrapers | Sequential | Prefect concurrent tasks (10 at once) | Same |

The VPS-only path is viable to at least $10K MRR given daily batch ingest and moderate API traffic. The migration pressure point is database: if concurrent API requests during nightly ingest cause latency spikes, add pgBouncer first before any infrastructure expansion.

---

## Technology Decisions Summary

| Component | Technology | Confidence | Rationale |
|-----------|-----------|------------|-----------|
| Database | PostgreSQL 16+ | HIGH | Concurrent reads/writes, native upsert, tsvector FTS |
| Schema migrations | Alembic | HIGH | Standard SQLAlchemy migration tool |
| Pipeline orchestration | Prefect (self-hosted) | HIGH | Python-native, lightweight, good solo-operator DX |
| Scraping (state portals) | Scrapling | MEDIUM | Already chosen, anti-bot bypass, not yet validated at scale |
| Rate limiting | slowapi + Redis (or in-process first) | HIGH | slowapi is the standard FastAPI rate limiting library |
| FTS | PostgreSQL tsvector + GIN index | HIGH | Eliminates manual rebuild, better ranking than FTS5 |
| API framework | FastAPI (keep) | HIGH | No reason to change; Pydantic v2 improvements are additive |
| Response models | Pydantic v2 `from_attributes=True` | HIGH | Eliminates fragile hand-rolled dict serializer |

---

## Sources

- [Airbyte: Data as a Service](https://airbyte.com/data-engineering-resources/data-as-a-service)
- [Prefect Open Source](https://www.prefect.io/prefect/open-source)
- [ZenML: Dagster vs Prefect vs Airflow](https://www.zenml.io/blog/orchestration-showdown-dagster-vs-prefect-vs-airflow)
- [Forage.ai: Scalable Web Data Extraction](https://forage.ai/blog/scalable-web-data-extraction-pipeline/)
- [UK Data Services: Python Data Pipeline Tools](https://ukdataservices.co.uk/blog/articles/python-data-pipeline-tools-2025)
- [slowapi on GitHub](https://github.com/laurentS/slowapi)
- [Zuplo: API Rate Limiting Best Practices](https://zuplo.com/learning-center/10-best-practices-for-api-rate-limiting-in-2025)
- [PostgreSQL FTS performance (Hacker News)](https://news.ycombinator.com/item?id=43627646)
- [Airbyte: ETL Deduplication](https://airbyte.com/data-engineering-resources/the-best-way-to-handle-data-deduplication-in-etl)
- [FastAPI SQL Databases docs](https://fastapi.tiangolo.com/tutorial/sql-databases/)

---

*Architecture research: 2026-03-24*
