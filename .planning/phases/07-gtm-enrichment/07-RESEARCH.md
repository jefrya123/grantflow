# Phase 7: GTM + Enrichment - Research

**Researched:** 2026-03-24
**Domain:** Landing page, pricing page, API playground, usage analytics middleware, LLM topic categorization
**Confidence:** HIGH (stack is well-understood; project codebase reviewed directly)

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| QUAL-04 | LLM-powered categorization tags opportunities by topic/sector | instructor + OpenAI Batch API; new `topic_tags` Text column + migration 0006; background enrichment job wired into APScheduler |
| GTM-01 | Landing page explaining product value proposition | New Jinja2 template `landing.html`; `/` route currently redirects to `/search` — redirect becomes the landing page instead; existing CSS extended |
| GTM-02 | Pricing page with coverage-based tiers (not call volume) | New Jinja2 template `pricing.html`; static route `/pricing`; no Stripe wiring — display only |
| GTM-03 | Interactive API playground (try-it-now, no account) | HTML + vanilla JS page calling `/api/v1/opportunities/search` with a built-in demo key; bypass `get_api_key` dependency for playground key or use a hard-coded read-only key |
| GTM-04 | Usage analytics tracking (endpoint hits, search queries, API key usage) | `@app.middleware("http")` decorator + background task writing to new `api_events` PostgreSQL table; structured log fields: endpoint, method, api_key_prefix, query_params, status_code, duration_ms |
</phase_requirements>

---

## Summary

Phase 7 is the GTM launch layer on top of a working product. It breaks into four distinct work streams:
(1) public-facing Jinja2 pages (landing, pricing, playground),
(2) an analytics event store (new DB table + non-blocking middleware),
(3) LLM-powered topic tagging using the instructor library + OpenAI Batch API, and
(4) wiring topic tags into search filters and the API schema.

The stack stays completely within the existing conventions: FastAPI, Jinja2, PostgreSQL, SQLAlchemy ORM, Alembic, and Pydantic v2. No new frontend framework is introduced. The playground is vanilla JS calling the live API — no build step, no npm. LLM enrichment runs as a background/scheduled job, never blocking request handling. The existing `@app.middleware("http")` decorator pattern (already proven in this codebase) handles analytics without `BaseHTTPMiddleware` limitations.

**Primary recommendation:** Build all four streams as separate plans (pages, analytics, LLM enrichment, search integration). Analytics and pages can be planned in parallel; LLM enrichment depends on the new DB column being in place. Keep all pages server-rendered Jinja2 to match existing patterns — no new frontend tooling.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Jinja2 | >=3.1 (already installed) | Server-rendered landing, pricing, playground pages | Already in use for all web pages; consistent with existing templates |
| FastAPI | >=0.115 (already installed) | Route handlers for new pages | Already the app framework |
| SQLAlchemy | >=2.0 (already installed) | New `api_events` ORM model | Already used for all DB access |
| Alembic | >=1.14 (already installed) | Migration 0006 (topic_tags) + 0007 (api_events) | Already the migration tool |
| instructor | >=1.8 | Structured LLM outputs with Pydantic; batch classification | Gold standard for reliable LLM-to-Pydantic extraction; supports OpenAI Batch API natively |
| openai | >=1.0 | LLM API calls for topic categorization | Direct dependency of instructor; gpt-4o-mini for cost efficiency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio | stdlib | Concurrent LLM batch calls in enrichment job | Use for the async enrichment worker |
| BackgroundTasks / starlette Background | stdlib/starlette | Non-blocking analytics DB writes from middleware | Required because BaseHTTPMiddleware doesn't support BackgroundTasks directly |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| instructor | raw openai client + manual Pydantic parsing | instructor handles retries, validation failures, and batch API formatting automatically; raw client requires hand-rolling all of that |
| OpenAI Batch API | real-time per-record LLM calls | Batch API costs 50% less and is perfect for enriching existing records offline; real-time calls would block ingestion |
| vanilla JS playground | Swagger UI (/docs) | /docs already exists but requires knowing your own API key; the playground provides a zero-friction demo experience with a built-in read-only key |
| custom analytics table | Apitally / external service | Self-hosted table keeps all data in the existing PostgreSQL; no external dependency, data accessible for custom queries |

**Installation (new deps only):**
```bash
uv add instructor openai
```

---

## Architecture Patterns

### Recommended Project Structure (additions only)
```
grantflow/
├── enrichment/
│   ├── __init__.py
│   ├── tagger.py          # LLM topic tagging logic (instructor + OpenAI)
│   └── run_enrichment.py  # CLI entrypoint + scheduler integration
├── analytics/
│   ├── __init__.py
│   └── middleware.py      # @app.middleware("http") analytics capture
templates/
├── landing.html           # GTM-01: hero, value prop, CTA to /pricing and /search
├── pricing.html           # GTM-02: coverage-based tier display (no Stripe)
└── playground.html        # GTM-03: vanilla JS try-it-now UI
```

### Pattern 1: Analytics Middleware — Non-Blocking DB Write

**What:** `@app.middleware("http")` decorator intercepts every request; after response is sent, a background task writes one row to `api_events`.

**When to use:** Any time you need zero-latency-impact request instrumentation.

**Critical constraint:** `BaseHTTPMiddleware` does NOT support `BackgroundTasks`. Use the `@app.middleware("http")` decorator form instead, which allows `response.background = BackgroundTask(fn, args)` assignment.

```python
# Source: FastAPI official docs + GitHub discussion #4947
from starlette.background import BackgroundTask
from sqlalchemy.orm import Session

@app.middleware("http")
async def analytics_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)

    # Non-blocking: runs AFTER response is sent to client
    response.background = BackgroundTask(
        record_api_event,
        path=request.url.path,
        method=request.method,
        api_key_prefix=request.headers.get("x-api-key", "")[:8],
        query_string=str(request.url.query),
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    return response
```

**DB session in background task:** Cannot use FastAPI `Depends(get_db)` inside middleware background tasks. Must create a `SessionLocal()` directly and close it manually.

### Pattern 2: LLM Topic Tagging with instructor + OpenAI Batch API

**What:** instructor wraps the OpenAI client to enforce Pydantic output schemas. For bulk enrichment, use the OpenAI Batch API (50% cost discount, 24h turnaround).

**When to use:** Enriching existing records overnight; never during request handling.

```python
# Source: https://python.useinstructor.com/examples/classification/
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel

class TopicTags(BaseModel):
    topics: list[str]   # e.g. ["health", "small_business", "research"]
    sector: str         # e.g. "federal_health"

client = instructor.from_provider("openai", async_client=True)

async def tag_opportunity(title: str, description: str) -> TopicTags:
    return await client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=TopicTags,
        messages=[{
            "role": "user",
            "content": f"Categorize this grant opportunity.\nTitle: {title}\nDescription: {description[:500]}"
        }]
    )
```

**Batch approach for bulk enrichment (preferred):** Use `instructor`'s batch CLI or the OpenAI Batch API directly for records where `topic_tags IS NULL`. Submit JSONL, poll for completion, write results back to DB.

### Pattern 3: Landing + Pricing Pages (Jinja2)

**What:** Static Jinja2 templates served at `/` (landing) and `/pricing`. No auth, no DB queries needed except optionally a record count for social proof.

**When to use:** These are purely marketing pages — no complex logic.

```python
# web/routes.py additions
@router.get("/")
def landing_page(request: Request, db: Session = Depends(get_db)):
    total_opps = db.query(func.count(Opportunity.id)).scalar()
    return templates.TemplateResponse(request, "landing.html", {
        "total_opps": total_opps,
    })

@router.get("/pricing")
def pricing_page(request: Request):
    return templates.TemplateResponse(request, "pricing.html", {})
```

Note: The current `/` redirects to `/search`. Landing page replaces that redirect.

### Pattern 4: API Playground (no auth)

**What:** A Jinja2 HTML page with vanilla JS that sends a live fetch() to `/api/v1/opportunities/search`. Uses a hard-coded read-only demo key (stored in env as `GRANTFLOW_DEMO_API_KEY`) that is excluded from rate limit counts or given a high limit.

**Options for the demo key:**
- Option A: Pre-provision a key in the `api_keys` table tagged as `tier="demo"` with a very high limit. The `get_api_key` dependency accepts it normally.
- Option B: Add a bypass in `get_api_key` middleware that checks for the demo key header and skips the hash lookup (simpler, but slightly less clean).

**Recommendation: Option A** — provision a `demo` tier key in the DB (created via a setup script/migration seed). This keeps all auth flows consistent and the tier controls its own rate limit.

```html
<!-- playground.html excerpt -->
<script>
const DEMO_KEY = "{{ demo_api_key }}";  {# injected from env at render time #}
async function runQuery() {
    const q = document.getElementById('query').value;
    const res = await fetch(`/api/v1/opportunities/search?q=${encodeURIComponent(q)}&per_page=5`, {
        headers: { 'X-API-Key': DEMO_KEY }
    });
    const data = await res.json();
    document.getElementById('output').textContent = JSON.stringify(data, null, 2);
}
</script>
```

### Anti-Patterns to Avoid

- **BaseHTTPMiddleware for analytics:** Has known issues with background tasks and streaming responses. Use `@app.middleware("http")` instead.
- **Synchronous LLM calls in request path:** Never call the LLM synchronously during an API request. All enrichment runs as a scheduled/background job.
- **Writing topic_tags into `category` column:** `category` holds the funding instrument category (Discretionary, Mandatory, etc.). Topic tags go in a NEW `topic_tags` Text column (JSON array of strings).
- **Hard-coding the demo API key in Python source:** Use an env var (`GRANTFLOW_DEMO_API_KEY`). Pass it to the playground template at render time.
- **Enriching all records per run:** Query `WHERE topic_tags IS NULL LIMIT 500` per job run to avoid runaway LLM costs.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured LLM output parsing | Custom JSON extract + regex | instructor | Handles retries on parse failure, validation errors, schema enforcement automatically |
| LLM batch job submission | Manual JSONL + polling loop | instructor batch CLI + OpenAI Batch API | OpenAI Batch API handles job lifecycle; instructor formats the requests correctly |
| Analytics aggregation | Custom SQL GROUP BY dashboard | Direct SQL queries on `api_events` table | The table is in Postgres; standard SQL GROUP BY is sufficient for v1 analytics views |
| Per-tier rate limiting | Custom counter logic | slowapi (already installed) — add `demo` tier with high limit | Already the rate limiting solution; adding a tier means adding a DB row + config, not new code |

**Key insight:** All tooling for this phase is already installed (FastAPI, Jinja2, SQLAlchemy, slowapi, APScheduler) except `instructor` and `openai`. The only net-new infrastructure is two DB tables and the enrichment module.

---

## Common Pitfalls

### Pitfall 1: BaseHTTPMiddleware + BackgroundTasks Incompatibility
**What goes wrong:** If you use `class AnalyticsMiddleware(BaseHTTPMiddleware)`, you cannot attach `BackgroundTasks` to the response — the task runs in the wrong scope and the DB session may be closed by the time it executes.
**Why it happens:** `BaseHTTPMiddleware` wraps ASGI calls differently; the background task lifecycle doesn't align with the response lifecycle.
**How to avoid:** Use `@app.middleware("http")` decorator form exclusively. Assign `response.background = BackgroundTask(fn, ...)` before returning.
**Warning signs:** `DetachedInstanceError` or `Session already closed` errors in analytics writes.

### Pitfall 2: DB Session in Middleware Background Tasks
**What goes wrong:** Using `Depends(get_db)` in a background task queued from middleware — `Depends` only works in route handlers.
**Why it happens:** FastAPI's dependency injection is route-scoped, not middleware-scoped.
**How to avoid:** Import `SessionLocal` directly from `grantflow.database` and create/close it explicitly inside the background task function.

### Pitfall 3: LLM Enrichment Runaway Costs
**What goes wrong:** Enrichment job processes ALL `topic_tags IS NULL` records on every run — with 80K+ opportunities this gets expensive fast.
**Why it happens:** No pagination/cap on the enrichment query.
**How to avoid:** Always use `LIMIT 500` (or a configurable `ENRICHMENT_BATCH_SIZE` env var) per job run. First run processes oldest records; subsequent runs continue incrementally.

### Pitfall 4: topic_tags Column Conflicts with Existing `category`
**What goes wrong:** Developer stores LLM topics in `Opportunity.category` because it seems like the right field.
**Why it happens:** Column naming ambiguity between the funding instrument category and LLM-derived semantic topics.
**How to avoid:** Add a new `topic_tags` Text column (stores JSON array string like `["health", "research"]`). Never modify `category` in this phase.

### Pitfall 5: Playground Demo Key Leakage
**What goes wrong:** Demo API key is hard-coded in the HTML template source and committed to git.
**Why it happens:** Convenience during development.
**How to avoid:** Always inject from `os.getenv("GRANTFLOW_DEMO_API_KEY")` in the route handler. Add the key to `.env` (gitignored). Consider provisioning a separate read-only key with tight rate limits.

### Pitfall 6: Analytics Table Slowing Down High-Traffic Endpoints
**What goes wrong:** The background analytics write adds measurable latency when PostgreSQL is under load.
**Why it happens:** Even "background" tasks run before the connection is fully returned to the pool.
**How to avoid:** (a) Use a separate DB connection pool or session factory for analytics writes — don't share the main `SessionLocal`. (b) Consider a simple in-memory queue (collections.deque) that's flushed in batches every 60s by APScheduler if latency becomes an issue. For v1, direct background writes are fine.

---

## Code Examples

### New `api_events` Table Model
```python
# grantflow/models.py — add after ApiKey class
class ApiEvent(Base):
    __tablename__ = "api_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ts = Column(Text, nullable=False, index=True)          # ISO 8601 UTC
    path = Column(Text, nullable=False)                     # e.g. /api/v1/opportunities/search
    method = Column(Text, nullable=False)                   # GET, POST, etc.
    api_key_prefix = Column(Text, nullable=True, index=True)  # first 8 chars only
    query_string = Column(Text, nullable=True)              # raw query string
    status_code = Column(Integer, nullable=False)
    duration_ms = Column(Integer, nullable=False)
```

### topic_tags Column (Opportunity model addition)
```python
# grantflow/models.py — add to Opportunity class
topic_tags = Column(Text, nullable=True)  # JSON array: '["health", "sbir", "research"]'
```

### Alembic Migrations
- Migration 0006: `ALTER TABLE opportunities ADD COLUMN topic_tags TEXT`
- Migration 0007: `CREATE TABLE api_events (id SERIAL PK, ts TEXT, path TEXT, method TEXT, api_key_prefix TEXT, query_string TEXT, status_code INT, duration_ms INT)` + index on `ts` and `api_key_prefix`

### instructor Batch Classification (enrichment job)
```python
# grantflow/enrichment/tagger.py
import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel
import asyncio, json

TOPICS = ["health", "research", "education", "environment", "housing",
          "small_business", "agriculture", "transportation", "defense", "arts"]

class TopicTags(BaseModel):
    topics: list[str]   # subset of TOPICS list above
    sector: str         # free-form sector label

client = instructor.from_provider("openai", async_client=True)

async def tag_single(opp_id: str, title: str, description: str) -> tuple[str, TopicTags]:
    tags = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_model=TopicTags,
        messages=[{"role": "user", "content":
            f"Assign topic tags to this government grant.\n"
            f"Valid topics: {', '.join(TOPICS)}\n"
            f"Title: {title}\nDescription: {(description or '')[:400]}"
        }]
    )
    return opp_id, tags

async def tag_batch(records: list[dict]) -> list[tuple[str, TopicTags]]:
    tasks = [tag_single(r["id"], r["title"], r["description"]) for r in records]
    return await asyncio.gather(*tasks, return_exceptions=False)
```

### Search Filter Extension for topic_tags
```python
# grantflow/api/query.py — add to build_opportunity_query()
if topic:
    query = query.filter(Opportunity.topic_tags.ilike(f'%"{topic}"%'))
```
Note: JSON string contains `["health", "sbir"]`; `ilike` on the serialized string is acceptable for v1 since it's indexed. A proper `GIN + jsonb` index would be v2 if query volume demands it.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual rule-based categorization | LLM-based with structured outputs (instructor) | 2024–2025 | Categorical labels from free text without hand-crafted rules |
| Logging middleware via BaseHTTPMiddleware | `@app.middleware("http")` + BackgroundTask | FastAPI 0.95+ | Eliminates background task scope bugs |
| Custom JSON parsing of LLM outputs | instructor + Pydantic BaseModel | 2023–present | Automatic retries, validation, zero boilerplate |
| Real-time LLM per request | Offline batch enrichment + cached column | 2024 DaaS pattern | 50x cheaper; latency irrelevant for enrichment |

**Deprecated/outdated:**
- `BaseHTTPMiddleware` for analytics: still works but has documented issues with streaming + BackgroundTasks; prefer `@app.middleware("http")`.
- Storing structured data as raw dicts in SQLAlchemy `Text` column and parsing at query time: for v1 with moderate volume this is fine; in v2 migrate to `JSONB` with GIN index for proper JSON querying.

---

## Open Questions

1. **Demo API key provisioning strategy**
   - What we know: A key must exist in `api_keys` table before the playground works; it should have a permissive rate limit.
   - What's unclear: Should the demo key be seeded via Alembic migration data, a `setup.py` script, or a manual CLI command?
   - Recommendation: Add a seed script `scripts/seed_demo_key.py` that's idempotent (checks for existing demo key before inserting). Document in README. Do NOT use a migration for data seeding.

2. **Analytics table retention / size**
   - What we know: `api_events` will grow unbounded; at 1000 req/day free tier × many keys = potentially millions of rows.
   - What's unclear: No retention policy has been defined.
   - Recommendation: For v1, add a `created_at` index and document that rows older than 90 days can be deleted. A cleanup job can be v2.

3. **LLM provider choice: OpenAI vs alternatives**
   - What we know: OpenAI gpt-4o-mini is the cost-efficient standard; instructor supports Anthropic, Gemini, Ollama too.
   - What's unclear: The project has no existing LLM API key or provider decision.
   - Recommendation: Default to OpenAI gpt-4o-mini. Gate the entire enrichment job on `OPENAI_API_KEY` env var being set — skip silently if absent (same pattern as `SAM_API_KEY`). This means QUAL-04 is functional only when the operator provides an API key.

4. **topic filter on `/search` web page**
   - What we know: `topic_tags` will be a new filterable field.
   - What's unclear: Should the web UI `/search` page gain a new topic filter dropdown, or is this API-only for v1?
   - Recommendation: Add a simple topic filter dropdown to the web search page in the same plan that adds the `topic` query param to the API. This satisfies GTM success criterion 5 ("searchable and filterable").

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_analytics.py tests/test_enrichment.py tests/test_gtm_pages.py -x` |
| Full suite command | `uv run pytest tests/ -x` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GTM-01 | `/` returns landing page HTML with value prop content | unit/integration | `uv run pytest tests/test_gtm_pages.py::test_landing_page -x` | Wave 0 |
| GTM-02 | `/pricing` returns pricing page HTML with tier names | unit/integration | `uv run pytest tests/test_gtm_pages.py::test_pricing_page -x` | Wave 0 |
| GTM-03 | `/playground` renders with demo key injected (no 500) | unit/integration | `uv run pytest tests/test_gtm_pages.py::test_playground_page -x` | Wave 0 |
| GTM-04 | Analytics middleware writes an `api_events` row after a search request | integration | `uv run pytest tests/test_analytics.py::test_event_recorded -x` | Wave 0 |
| QUAL-04 | `tag_opportunity()` returns a `TopicTags` with non-empty topics list | unit (mocked) | `uv run pytest tests/test_enrichment.py::test_tag_opportunity_mock -x` | Wave 0 |
| QUAL-04 | Opportunities with `topic_tags` set are filterable via API `?topic=health` | integration | `uv run pytest tests/test_enrichment.py::test_topic_filter -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_analytics.py tests/test_enrichment.py tests/test_gtm_pages.py -x`
- **Per wave merge:** `uv run pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_gtm_pages.py` — covers GTM-01, GTM-02, GTM-03
- [ ] `tests/test_analytics.py` — covers GTM-04 (middleware event recording)
- [ ] `tests/test_enrichment.py` — covers QUAL-04 (mocked LLM + topic filter)
- [ ] `scripts/seed_demo_key.py` — idempotent demo key provisioning (needed before test_gtm_pages.py can test playground)

---

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection — `grantflow/models.py`, `grantflow/app.py`, `grantflow/api/routes.py`, `grantflow/api/schemas.py`, `grantflow/web/routes.py`, `templates/` — current project state
- FastAPI official docs (background tasks, middleware) — `https://fastapi.tiangolo.com/tutorial/background-tasks/`
- GitHub fastapi/fastapi discussion #4947 — BackgroundTasks in middleware pattern

### Secondary (MEDIUM confidence)
- instructor library PyPI + official docs — `https://python.useinstructor.com/` — classification examples, batch processing, async support (version 1.8.1 confirmed on PyPI)
- OpenAI Batch API — `https://developers.openai.com/api/docs` — 50% cost discount confirmed, 24h turnaround
- OpenAI gpt-4o-mini pricing — $0.15/$0.60 per million tokens input/output; Batch API halves this

### Tertiary (LOW confidence)
- WebSearch: FastAPI analytics middleware patterns — multiple Medium posts cross-verified with official Starlette docs
- WebSearch: SaaS pricing page best practices 2026 — multiple sources agree on outcome-first messaging and 3-tier display

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all dependencies already in pyproject.toml except instructor/openai; instructor is the documented standard for structured LLM outputs
- Architecture patterns: HIGH — middleware pattern verified against FastAPI docs and GitHub issues; LLM pattern verified against instructor official docs
- Pitfalls: HIGH — BaseHTTPMiddleware/BackgroundTask incompatibility is documented in official GitHub; session scope issue is standard SQLAlchemy knowledge
- LLM cost estimates: MEDIUM — pricing confirmed from OpenAI pricing page via WebSearch; token count per record is an estimate

**Research date:** 2026-03-24
**Valid until:** 2026-05-01 (instructor and OpenAI pricing change frequently; verify before implementation)
