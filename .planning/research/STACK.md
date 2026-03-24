# Technology Stack

**Project:** GrantFlow
**Researched:** 2026-03-24
**Scope:** Production upgrade recommendations for existing FastAPI + SQLite MVP

---

## Decision Summary

| Area | Current | Recommended | Action |
|------|---------|-------------|--------|
| Database | SQLite + FTS5 | PostgreSQL 16 + tsvector | Migrate |
| DB driver | sqlite (stdlib) | asyncpg 0.31.0 | Add |
| DB migrations | init_db() / raw DDL | Alembic 1.14+ | Add |
| Task scheduling | None (manual CLI) | APScheduler 3.11 | Add |
| Web scraping | httpx (basic) | Scrapling 0.4+ | Upgrade |
| Proxy rotation | None | Scrapling built-in + datacenter pool | Add |
| Logging | stdlib logging | structlog 24.x | Upgrade |
| Process manager | uvicorn --reload | Gunicorn + UvicornWorker | Upgrade |
| Reverse proxy | None | Nginx | Add |
| Core frameworks | FastAPI, SQLAlchemy, Pydantic | Keep all, upgrade SQLAlchemy async | Keep |

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | 0.135.2 (current) | HTTP API and web routing | Keep as-is; no upgrade needed |
| SQLAlchemy | 2.0.48 (current) | ORM + query engine | Enable async dialect — same version, different engine config |
| Pydantic | 2.12.5 (current) | Request/response validation | Keep as-is |
| uvicorn | 0.42.0 (current) | ASGI server | Keep; switch to Gunicorn-managed in prod |

### Database

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | 16 (LTS, even-numbered) | Primary data store | 100K+ rows with concurrent reads/writes during ingestion; tsvector GIN index replaces SQLite FTS5; WAL mode + single-writer bottleneck in SQLite is the critical failure point at scale |
| asyncpg | 0.31.0 | Async PostgreSQL driver | Required for SQLAlchemy async engine; 2,800 ops/sec vs 1,450 for sync ORM in benchmarks; enables non-blocking reads while ingestion writes |
| psycopg2-binary | 2.9.x | Sync driver (Alembic only) | Alembic migration runner uses sync connections; keep as dev/deploy dependency only |
| Alembic | 1.14+ | Schema migrations | `init_db()` pattern does not scale past MVP — no version tracking, no rollback, no CI safety. Alembic autogenerate works directly with SQLAlchemy 2.0 models |

**Why PostgreSQL over SQLite at this scale:**
- SQLite FTS5 rebuilds the entire virtual table on each ingest run (current `_rebuild_fts()` pattern); PostgreSQL tsvector columns update incrementally on row write via trigger
- SQLite WAL allows concurrent reads but only one writer — the daily ingest job (bulk upsert of 80K+ rows) will block all API reads for minutes
- Benchmarks: SQLite median query time is ~3x worse than PostgreSQL for complex filtered queries; 9 queries timed out at 60s on a comparable dataset
- PostgreSQL FTS at 100K documents: 5-10ms per query with GIN index, well within acceptable latency

**Why not Elasticsearch:**
Elasticsearch is operationally heavy (separate JVM process, 1GB+ RAM minimum, complex cluster management). PostgreSQL tsvector handles up to a few million documents comfortably and requires zero additional infrastructure. For this scale and a solo operator budget constraint, PostgreSQL FTS is the correct choice. Re-evaluate if document count exceeds 5M or faceted search complexity increases significantly.

### Task Scheduling

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| APScheduler | 3.11.2 | Daily ingestion cron | In-process scheduler; no Redis or separate worker process required; integrates via FastAPI lifespan; AsyncIOScheduler runs in same event loop |

**Why APScheduler 3.x over alternatives:**
- **Celery**: Requires Redis or RabbitMQ as a broker — operational overhead not justified for one daily job. Celery is the right choice at 10+ concurrent task types or distributed workers. Not warranted here.
- **APScheduler 4.x**: Pre-release; explicitly marked "do NOT use in production" by maintainers as of March 2026. Backwards-incompatible API changes still in progress.
- **System cron**: Works but creates deployment coupling (cron entries must be managed separately from app), no retry logic, no observability hooks. APScheduler keeps scheduling inside the application where it can share DB sessions and log to the same sink.
- **FastAPI BackgroundTasks**: Not a scheduler — fire-and-forget per request, not periodic.

**Pattern:** Register `AsyncIOScheduler` in FastAPI `lifespan`, add `cron` trigger for `run_all_ingestion()` at a fixed daily time. Store job state in PostgreSQL via `SQLAlchemyJobStore` (same DB, no extra infra).

### Web Scraping

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Scrapling | 0.4+ | State portal scraping | Purpose-built for adaptive scraping; built-in proxy rotation; Cloudflare Turnstile bypass out of the box; 92% test coverage; used in production by hundreds of scrapers |
| httpx | 0.28.1 (current) | Federal API calls (Grants.gov, USAspending, SBIR) | Keep for structured API calls — no scraping needed, no reason to replace |

**Why Scrapling over alternatives for state portals:**
- Government portals typically have minimal bot protection (Tier 1 in proxy classification), but some state portals use Cloudflare. Scrapling's headless mode handles this without manual intervention.
- Built-in `ProxyRotator` with cyclic/custom strategies eliminates rolling your own rotation logic.
- "Adaptive selectors" — the parser re-locates elements when page HTML changes, reducing scraper maintenance burden. This matters operationally: government sites redesign without warning.
- Released v0.4 February 2026 with full async support — compatible with FastAPI's async architecture.

**Keep httpx for:** All structured API calls (Grants.gov XML bulk download, USAspending REST, SBIR JSON). These are server-to-server with known schemas — Scrapling's browser overhead is unnecessary.

### Proxy Infrastructure

| Technology | Purpose | Why |
|------------|---------|-----|
| Scrapling built-in ProxyRotator | Rotation logic | No custom code needed |
| Webshare or Decodo datacenter proxies | IP pool | Government portals are Tier 1 (public data, minimal bot detection); datacenter proxies are sufficient and cost ~$0.10-0.50/IP/month vs $2-15/GB for residential; start with 10-20 IPs |

**Decision:** Start with datacenter proxies. If a specific state portal blocks datacenter IPs, add residential proxies for that source only (hybrid approach). Do not pay for residential proxies across the board until blocked.

### Logging

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| structlog | 24.x | Application and ingestion logging | stdlib `logging` produces unstructured text; structlog emits JSON in production (machine-parseable) and colored key-value pairs in development (human-readable) with same code path; better observability tooling integration than loguru |

**Why structlog over loguru:**
- loguru is easier to configure but produces less structured output by default and lacks first-party OpenTelemetry integration (relevant if monitoring is added later)
- structlog's context binding is ideal for ingestion pipelines: bind `source="grants_gov"` once, all subsequent log calls carry it
- Wraps stdlib `logging` so third-party libraries (SQLAlchemy, httpx, APScheduler) log into the same pipeline

### Production Serving

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Gunicorn | 23.x | Process manager | Spawns multiple UvicornWorker processes; handles SIGTERM/graceful shutdown; restarts dead workers; industry-standard for FastAPI on VPS |
| Nginx | 1.26+ | Reverse proxy | SSL termination, static file serving, request buffering; keeps Python workers focused on app logic |
| systemd | (OS-managed) | Service supervision | Ensures Gunicorn restarts on crash and starts on boot; standard on Ubuntu 24.04 (Hetzner) |

**Worker count for Hetzner CX22 (2 vCPU, 4GB RAM):**
Formula: `(2 * cores) + 1 = 5 workers`. With a lean FastAPI app (~100-150MB per worker), 5 workers uses ~750MB leaving ample headroom for PostgreSQL (running on same host initially). Start with `--workers 3` and tune upward.

**Do not use `uvicorn --reload` in production.** That flag is dev-only (file watcher overhead).

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Database | PostgreSQL 16 | SQLite (keep) | Single-writer WAL blocks API reads during bulk ingest; FTS5 requires full rebuild; no migration tooling |
| Database | PostgreSQL 16 | MySQL/MariaDB | PostgreSQL FTS (tsvector) is significantly better than MySQL FULLTEXT; JSONB support for `raw_data` column |
| FTS | PostgreSQL tsvector | Elasticsearch | JVM process, 1GB+ RAM overhead, complex ops — unjustified for 100K docs and solo operator |
| FTS | PostgreSQL tsvector | Meilisearch | External service dependency; PostgreSQL FTS sufficient at this scale |
| Scheduling | APScheduler 3.x | Celery + Redis | Broker infra overhead; Celery is overkill for one daily job |
| Scheduling | APScheduler 3.x | APScheduler 4.x | Pre-release, not production-safe as of March 2026 |
| Scheduling | APScheduler 3.x | System cron | No retry, no observability, deployment coupling |
| Scraping | Scrapling | Playwright + custom | Scrapling wraps Playwright with adaptive selectors and built-in proxy rotation; lower maintenance |
| Scraping | Scrapling | Scrapy | Heavy framework; batch-oriented; Scrapling's async + adaptive approach fits better for scattered gov portals |
| Logging | structlog | loguru | loguru simpler but weaker structured output; no first-party OTEL integration |
| Logging | structlog | stdlib logging | Unstructured text; harder to parse in production; already in use and it's showing its limits |

---

## What to Keep (No Change)

| Technology | Reason |
|------------|--------|
| FastAPI 0.135.2 | Current, stable, no gaps |
| Pydantic 2.12.5 | Current, stable, no gaps |
| uvicorn 0.42.0 | Keep for local dev; Gunicorn wraps it in prod |
| httpx 0.28.1 | Keep for all structured API calls |
| Jinja2 3.1.6 | Keep for search UI; no reason to replace with SPA |
| python-dotenv 1.2.2 | Keep; sufficient for config |
| uv | Keep as package manager; fast, reliable |
| Python 3.12+ | Keep; 3.13 is available but 3.12 is stable LTS |

---

## Installation

```bash
# Core additions
uv add "asyncpg>=0.31.0"
uv add "psycopg2-binary>=2.9"
uv add "alembic>=1.14"
uv add "apscheduler>=3.11,<4.0"
uv add "scrapling>=0.4"
uv add "structlog>=24.0"

# Production serving (system packages on VPS, not uv)
# apt install nginx
# pip install gunicorn  (or uv add --group prod)

# Dev dependencies
uv add --dev "pytest-asyncio>=0.24"
```

---

## Migration Notes

**SQLite to PostgreSQL:** The existing SQLAlchemy models use `GRANTFLOW_DATABASE_URL` — swapping to a PostgreSQL connection string is the only code change needed at the model layer. The FTS layer requires replacing raw `FTS5` SQL with PostgreSQL `tsvector` column + GIN index + `to_tsquery()` calls (isolated to `database.py` and route FTS query logic). Alembic should be initialized before migration to capture the initial schema as revision `0001`.

**Async migration:** SQLAlchemy's async engine requires `async_sessionmaker` and `AsyncSession` — this is an API change in `database.py` and all `get_db()` callers. The trade-off: async adds complexity but enables concurrent reads during ingest writes. Given the daily ingest job writes 80K+ rows, this is worth the complexity.

---

## Confidence Assessment

| Decision | Confidence | Basis |
|----------|------------|-------|
| PostgreSQL over SQLite | HIGH | Official SQLite docs acknowledge limits; multiple 2026 benchmarks; WAL single-writer constraint is architectural fact |
| asyncpg 0.31.0 | HIGH | PyPI current version confirmed; SQLAlchemy 2.0 docs confirm compatibility |
| Alembic for migrations | HIGH | Industry standard for SQLAlchemy projects; widely documented with FastAPI |
| APScheduler 3.11 (not 4.x) | HIGH | Maintainer explicitly warns against 4.x in production; PyPI confirms 3.11.2 is stable |
| Scrapling 0.4+ | MEDIUM | February 2026 release confirmed on PyPI; production adoption claims from Apify blog; v0.4 async support confirmed in docs; relatively new so ecosystem maturity is medium |
| Datacenter proxies for gov sites | MEDIUM | Multiple proxy guides classify government portals as Tier 1 minimal-protection; but individual state portals may vary — validate per-portal |
| structlog over loguru | MEDIUM | Well-supported position in community; both are production-viable; structlog chosen for OTEL path and context binding pattern |
| PostgreSQL tsvector over Elasticsearch | HIGH | Neon benchmarks confirm 5-10ms at 100K docs with GIN index; multiple teams document replacing Elasticsearch with Postgres FTS at comparable scale |
| Gunicorn + Nginx deployment | HIGH | FastAPI official docs recommend this pattern; widely documented for Ubuntu VPS; systemd supervision is OS-standard |

---

## Sources

- [SQLite in Production? Not So Fast for Complex Queries](https://yyhh.org/blog/2026/01/sqlite-in-production-not-so-fast-for-complex-queries/) — 2026 benchmark showing 3x worse median query time and 9 query timeouts
- [PostgreSQL vs SQLite - selecthub 2026](https://www.selecthub.com/relational-database-solutions/postgresql-vs-sqlite/)
- [Comparing Native Postgres, ElasticSearch, and pg_search - Neon](https://neon.com/blog/postgres-full-text-search-vs-elasticsearch) — 5-10ms FTS at 100K rows with GIN index
- [Full Text Search over Postgres vs Elasticsearch - ParadeDB](https://www.paradedb.com/blog/elasticsearch-vs-postgres)
- [asyncpg PyPI](https://pypi.org/project/asyncpg/) — version 0.31.0 confirmed
- [Python + PostgreSQL: SQLAlchemy vs asyncpg Performance Comparison](https://dasroot.net/posts/2026/02/python-postgresql-sqlalchemy-asyncpg-performance-comparison/) — 2,800 ops/sec asyncpg benchmark
- [APScheduler PyPI](https://pypi.org/project/APScheduler/) — 3.11.2 stable, 4.0.0a1 alpha
- [APScheduler migration docs](https://apscheduler.readthedocs.io/en/master/migration.html) — explicit "do not use 4.x in production" warning
- [Scheduling Tasks in Python: APScheduler vs Celery Beat - Leapcell](https://leapcell.io/blog/scheduling-tasks-in-python-apscheduler-vs-celery-beat)
- [Scrapling PyPI](https://pypi.org/project/scrapling/) — version 0.4+ confirmed
- [Scrapling: The Adaptive Python Web Scraping Framework - Apify](https://use-apify.com/blog/scrapling-python-web-scraping-framework) — February 2026 v0.4, production validation
- [Scrapling documentation](https://scrapling.readthedocs.io/en/latest/index.html)
- [Proxy Rotation for Web Scraping 2026 - Apify](https://use-apify.com/blog/proxy-rotation-web-scraping-guide) — government portals as Tier 1
- [Residential vs Datacenter Proxies for Web Scraping 2026 - DEV Community](https://dev.to/wisdomudo/residential-vs-datacenter-proxies-for-web-scraping-which-one-delivers-better-roi-in-2026-17j0)
- [Python Logging with Structlog - Last9](https://last9.io/blog/python-logging-with-structlog/)
- [Best Python Logging Libraries - Better Stack](https://betterstack.com/community/guides/logging/best-python-logging-libraries/)
- [FastAPI Deployment Guide 2026 - ZestMinds](https://www.zestminds.com/blog/fastapi-deployment-guide/)
- [How Many Uvicorn Workers - LogicLoopTech](https://www.logiclooptech.dev/how-many-uvicorn-workers-do-you-actually-need-fastapi-performance-guide)
- [FastAPI official deployment docs](https://fastapi.tiangolo.com/deployment/)
- [Alembic auto-generate docs](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)
