# Phase 9: API & Feature Polish - Research

**Researched:** 2026-03-24
**Domain:** FastAPI / slowapi dynamic rate limiting, Pydantic schema extension, APScheduler job wiring
**Confidence:** HIGH

## Summary

Phase 9 closes four precisely-scoped gaps identified by the v1.0 audit. All four gaps live in files that already exist and are already tested — this is surgical editing, not new construction. No new libraries are needed; every required capability is already installed and used elsewhere in the codebase.

The most technically nuanced gap is API-02 (tier-aware rate limits). The audit note "slowapi does not support dynamic per-key limits" is **incorrect** — this was the Phase 3 rationale for deferring it, but the installed slowapi (>=0.1.9) does support callable `limit_value`. The `@limiter.limit()` decorator accepts a callable that receives the API key string (via `key_func`) and returns the limit string. The callable must do a DB lookup to resolve the tier, which requires using `SessionLocal()` directly (not FastAPI's `Depends(get_db)`, which is unavailable in the limiter callback context).

The other three gaps are straightforward: add `topic: str | None` parameter to `export_opportunities()`, add `canonical_id` field to `OpportunityResponse`, and add one `scheduler.add_job()` call in `app.py`'s `lifespan()` for `run_enrichment` gated on `OPENAI_API_KEY`.

**Primary recommendation:** Implement all four gaps in two plans — Plan 01 handles the rate-limit callable + export topic filter (API-02, API-05), Plan 02 handles the schema field + enrichment scheduler (QUAL-03, QUAL-04).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| API-02 | Rate limiting per API key with configurable tiers (free=1000, starter=10000, growth=100000/day) | slowapi callable limit_value pattern; TIER_LIMITS already in auth.py; ApiKey.tier already in model |
| API-05 | Bulk export endpoint supports ?topic= filter matching search endpoint | build_opportunity_query() already has topic param; export_opportunities() just needs it wired |
| QUAL-03 | canonical_id included in OpportunityResponse API schema | canonical_id column exists in Opportunity model; only missing from OpportunityResponse Pydantic model |
| QUAL-04 | LLM enrichment runs on daily APScheduler job (gated on OPENAI_API_KEY) | run_enrichment() already exists; APScheduler pattern established in app.py lifespan |
</phase_requirements>

---

## Standard Stack

### Core (already installed — no new deps)

| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| slowapi | >=0.1.9 | Rate limiting with callable limit_value | Installed, used in app.py |
| APScheduler | >=3.11,<4.0 | Cron job scheduling | Installed, used in app.py |
| Pydantic v2 | (via FastAPI) | Response schema definition | Installed, all schemas use v2 |
| SQLAlchemy | (via grantflow) | DB session for tier lookup | Installed, SessionLocal available |

No new packages required for this phase.

---

## Architecture Patterns

### Pattern 1: slowapi Callable limit_value (API-02)

**What:** `@limiter.limit()` accepts a callable as `limit_value`. When the callable's signature includes a `key` parameter, slowapi passes `key_func(request)` to it at request time — in this app that is the `X-API-Key` header value (or IP for public routes).

**Verified from:** Direct inspection of `slowapi.wrappers.LimitGroup.__iter__` source code.

```python
# Source: slowapi.wrappers.LimitGroup.__iter__ (verified via source inspection)
# The callable receives key_function(request) when it has a `key` parameter:
#
#   if "key" in inspect.signature(self.__limit_provider).parameters.keys():
#       limit_raw = self.__limit_provider(self.key_function(self.request))
#
# key_function in this app is:
#   lambda request: request.headers.get("x-api-key", get_remote_address(request))
# So the callable receives the raw API key string (e.g. "gf_abc123...") or an IP.

def _tier_limit(key: str) -> str:
    """Dynamic rate limit string based on API key tier.

    Called by slowapi at each request. Must do its own DB lookup because
    FastAPI dependency injection is not available in this callback context.
    Uses SHA-256 hash to find the ApiKey row (same pattern as auth.py).
    """
    import hashlib
    from grantflow.database import SessionLocal
    from grantflow.models import ApiKey
    from grantflow.api.auth import TIER_LIMITS

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = SessionLocal()
    try:
        api_key = db.query(ApiKey).filter(
            ApiKey.key_hash == key_hash,
            ApiKey.is_active.is_(True),
        ).first()
        tier = api_key.tier if api_key else "free"
    finally:
        db.close()

    limit = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    return f"{limit}/day"
```

**Usage on each protected endpoint:**
```python
@router.get("/opportunities/search", ...)
@limiter.limit(_tier_limit)   # replaces @limiter.limit("1000/day")
def search_opportunities(...):
    ...
```

**Critical constraint:** The callable opens its own `SessionLocal()` and closes it in a `finally` block. This is consistent with the established pattern used in `analytics/middleware.py` (BackgroundTask also uses `SessionLocal()` directly, not `Depends(get_db)`).

**Export endpoint note:** The export route currently uses `@limiter.limit("100/day")` — a lower limit appropriate for bulk operations. The tier-aware version should preserve this differential (e.g., `f"{limit // 10}/day"`) or use a separate flat limit. Decision left to planner.

### Pattern 2: Export Topic Filter (API-05)

**What:** `build_opportunity_query()` in `api/query.py` already has `topic: str | None` parameter and already filters correctly. The search endpoint already passes it. The export endpoint simply omits it.

**Fix is a 3-line change to `export_opportunities()`:**
```python
# In routes.py export_opportunities():
# Add parameter:
topic: str | None = Query(default=None),

# Add to build_opportunity_query() call:
query = build_opportunity_query(
    db,
    ...existing params...,
    topic=topic,   # add this line
)
```

**The query filter in build_opportunity_query() (already verified):**
```python
if topic:
    query = query.filter(Opportunity.topic_tags.ilike(f'%"{topic}"%'))
```
This uses `ilike` with JSON-string quoting to match `"health"` inside `'["health","research"]'` — the same pattern as the search endpoint.

### Pattern 3: canonical_id in OpportunityResponse (QUAL-03)

**What:** `Opportunity.canonical_id` column exists in models.py (Text, nullable, indexed). `OpportunityResponse` in `api/schemas.py` does not include it. Adding it is a one-field addition to the Pydantic model.

```python
# In api/schemas.py OpportunityResponse, add after source_url:
canonical_id: Optional[str] = None
```

**Test impact:** `test_opportunity_response_preserves_exact_field_names` in `tests/test_schemas.py` asserts `expected_keys` exactly — `canonical_id` must be added to that set.

### Pattern 4: APScheduler Enrichment Job (QUAL-04)

**What:** `run_enrichment()` in `grantflow/enrichment/run_enrichment.py` already handles the OPENAI_API_KEY gate (returns silently if unset). It just needs a `scheduler.add_job()` call in `app.py`'s `lifespan()`.

**Established pattern from app.py:**
```python
# Source: grantflow/app.py lifespan() — existing job registration pattern
scheduler.add_job(
    lambda: asyncio.get_event_loop().run_in_executor(None, run_all_ingestion),
    CronTrigger(hour=2, minute=0, timezone="UTC"),
    id="daily_ingestion",
    replace_existing=True,
    misfire_grace_time=3600,
)
```

**Enrichment job (new — follows same pattern):**
```python
from grantflow.enrichment.run_enrichment import run_enrichment

scheduler.add_job(
    lambda: asyncio.get_event_loop().run_in_executor(None, run_enrichment),
    CronTrigger(hour=4, minute=0, timezone="UTC"),  # after daily ingestion at 02:00
    id="daily_enrichment",
    replace_existing=True,
    misfire_grace_time=3600,
)
```

`run_enrichment()` is synchronous (uses `asyncio.run()` internally for the OpenAI async calls). The `run_in_executor(None, ...)` wrapping is required — same reason as `run_all_ingestion`: prevents blocking the async event loop.

**OPENAI_API_KEY gate is already inside `run_enrichment()`** — no additional check needed at the scheduler level. If the env var is unset, the function logs a message and returns. The job registration is unconditional; silent no-ops are the correct behavior per the existing design decision.

### Recommended Edit Sequence

```
api/auth.py          — add _tier_limit() callable (or add to routes.py)
api/routes.py        — replace static "1000/day" with _tier_limit on all data routes
                       add topic= param to export_opportunities()
api/schemas.py       — add canonical_id to OpportunityResponse
app.py               — add scheduler.add_job for daily_enrichment in lifespan()
tests/test_auth_ratelimit.py   — add tier-aware limit tests
tests/test_export.py           — add topic filter test for export
tests/test_schemas.py          — add canonical_id to expected_keys set
```

### Anti-Patterns to Avoid

- **Storing tier in `request.state` from auth middleware:** The limiter callback runs before FastAPI dependencies resolve. `get_api_key` has not yet populated `request.state.api_key` when the limiter fires. DB lookup in `_tier_limit()` is required.
- **Using `asyncio.run()` in `_tier_limit()`:** The rate limiter callback is called in a sync context within the async event loop. `asyncio.run()` would raise `RuntimeError: This event loop is already running`. All DB operations in `_tier_limit()` must be synchronous (use `SessionLocal()` directly, not async session).
- **Placing `_tier_limit` inside the module scope of routes.py:** The function references `SessionLocal` which requires the DB to be initialized. It should be defined at module level but called lazily — this is fine since it opens a connection per-call, not at import time.
- **Forgetting to update the export rate limit:** The export endpoint uses `@limiter.limit("100/day")` — separate from the data endpoints' `"1000/day"`. If switching to `_tier_limit`, the export needs its own callable or a scaled variant to preserve the 10:1 ratio.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dynamic rate limits | Custom middleware checking tier before processing | slowapi callable `limit_value` | Already installed, handles counting/storage/429 response |
| Async job scheduling | Thread loop or custom cron | APScheduler `scheduler.add_job()` | Already wired in app.py lifespan |
| Pydantic ORM mapping | Manual `.to_dict()` | `model_validate(orm_obj)` + `from_attributes=True` | Already established pattern in schemas.py |

---

## Common Pitfalls

### Pitfall 1: Static rate limit string not replaced on all routes
**What goes wrong:** Replacing the decorator on `/search` but missing `/stats`, `/agencies`, `/export`, `/opportunities/{id}`. Each `@limiter.limit("1000/day")` must be individually replaced.
**How to avoid:** Grep for `@limiter.limit` to find all occurrences before editing.
**Warning sign:** Free and growth tier keys both get 429 at 1000 requests.

### Pitfall 2: _tier_limit DB session leak
**What goes wrong:** Exception path in `_tier_limit()` before `db.close()` — connection pool exhaustion under load.
**How to avoid:** Always use `try/finally` with `db.close()` in `finally`. The `run_enrichment()` pattern in the codebase already demonstrates this.

### Pitfall 3: test_opportunity_response_preserves_exact_field_names fails silently
**What goes wrong:** `canonical_id` added to `OpportunityResponse` but not added to `expected_keys` set in the test — test fails with unexpected key rather than "missing key", making the error message confusing.
**How to avoid:** Update test's `expected_keys` set when adding the field to the schema.

### Pitfall 4: Enrichment job blocks event loop
**What goes wrong:** `scheduler.add_job(run_enrichment, ...)` without `run_in_executor` — `run_enrichment()` calls `asyncio.run()` inside a running event loop, raising `RuntimeError`.
**How to avoid:** Always wrap sync functions with `lambda: asyncio.get_event_loop().run_in_executor(None, fn)` per the established pattern in app.py.

### Pitfall 5: Export topic filter not in CSV column list
**What goes wrong:** `?topic=health` filters results correctly but `topic_tags` is not in `_EXPORT_CSV_COLUMNS` — the CSV shows filtered results but users can't see what tags matched.
**How to avoid:** Consider adding `topic_tags` to `_EXPORT_CSV_COLUMNS` as part of this change (already in JSON export via `OpportunityResponse.model_dump()`).

---

## Code Examples

### Verifying the callable invocation contract (slowapi internals)

```python
# Source: slowapi.wrappers.LimitGroup.__iter__ (verified 2026-03-24)
# The "key" parameter name triggers the dynamic path:
def _tier_limit(key: str) -> str:  # "key" parameter name is significant
    ...
# Callable without "key" param is called with no args:
def _tier_limit() -> str:  # called as _tier_limit() — no request context available
    ...
```

### Minimal test for tier-aware limits

```python
# Pattern: create starter-tier key, verify it gets higher limit string
def test_tier_limit_callable_starter():
    """_tier_limit() returns correct string for starter tier."""
    from grantflow.api.auth import TIER_LIMITS
    # The callable must return "10000/day" for a starter key
    # Test via integration: make 1001 requests and verify no 429
    # (or unit-test the callable directly with a known key hash)
    ...
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|-----------------|--------|
| `@limiter.limit("1000/day")` flat | `@limiter.limit(_tier_limit)` callable | Enables per-tier enforcement |
| `topic=` param missing on export | Pass `topic=topic` through to `build_opportunity_query()` | Closes audit gap API-05 |
| `canonical_id` only in DB | Add to `OpportunityResponse` | Closes audit gap QUAL-03 |
| `run_enrichment()` CLI-only | Daily APScheduler job in `lifespan()` | Closes audit gap QUAL-04 |

---

## Open Questions

1. **Export rate limit scaling with tier**
   - What we know: Export currently has a separate lower limit (`100/day` vs `1000/day` for search).
   - What's unclear: Should the tier-aware callable apply a proportional limit to export too, or keep export flat at `100/day`?
   - Recommendation: Use a separate `_tier_export_limit` callable that returns `TIER_LIMITS[tier] // 10` (100/1000/10000 per day). Maintains the 10:1 ratio.

2. **Enrichment job timing relative to ingestion**
   - What we know: Daily ingestion runs at 02:00 UTC; enrichment should run after new records are ingested.
   - What's unclear: Whether `04:00 UTC` allows enough time for ingestion to complete on large datasets.
   - Recommendation: `04:00 UTC` gives a 2-hour buffer after ingestion, consistent with USAspending's 36h incremental window decision.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` |
| Quick run command | `uv run pytest tests/test_auth_ratelimit.py tests/test_export.py tests/test_schemas.py -x -q` |
| Full suite command | `uv run pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| API-02 | free tier gets 1000/day limit string | unit | `uv run pytest tests/test_auth_ratelimit.py::test_tier_limit_free -x` | Wave 0 |
| API-02 | starter tier gets 10000/day limit string | unit | `uv run pytest tests/test_auth_ratelimit.py::test_tier_limit_starter -x` | Wave 0 |
| API-02 | growth tier gets 100000/day limit string | unit | `uv run pytest tests/test_auth_ratelimit.py::test_tier_limit_growth -x` | Wave 0 |
| API-05 | export with ?topic= filter returns matching rows | integration | `uv run pytest tests/test_export.py::test_export_topic_filter -x` | Wave 0 |
| API-05 | export topic filter excludes non-matching rows | integration | `uv run pytest tests/test_export.py::test_export_topic_filter_excludes -x` | Wave 0 |
| QUAL-03 | canonical_id present in OpportunityResponse fields | unit | `uv run pytest tests/test_schemas.py::test_opportunity_response_preserves_exact_field_names -x` | ✅ (update existing) |
| QUAL-03 | canonical_id appears in GET /search response JSON | integration | `uv run pytest tests/test_schemas.py::test_canonical_id_in_api_response -x` | Wave 0 |
| QUAL-04 | daily_enrichment job registered in scheduler | unit | `uv run pytest tests/test_enrichment.py::test_enrichment_scheduler_job_registered -x` | Wave 0 |
| QUAL-04 | enrichment job uses run_in_executor pattern | unit | `uv run pytest tests/test_enrichment.py::test_enrichment_scheduler_job_registered -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest tests/test_auth_ratelimit.py tests/test_export.py tests/test_schemas.py tests/test_enrichment.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_auth_ratelimit.py` — add `test_tier_limit_free`, `test_tier_limit_starter`, `test_tier_limit_growth` (unit tests for `_tier_limit()` callable)
- [ ] `tests/test_export.py` — add `test_export_topic_filter`, `test_export_topic_filter_excludes`
- [ ] `tests/test_schemas.py` — update `test_opportunity_response_preserves_exact_field_names` to include `canonical_id` in `expected_keys`; add `test_canonical_id_in_api_response`
- [ ] `tests/test_enrichment.py` — add `test_enrichment_scheduler_job_registered`

---

## Sources

### Primary (HIGH confidence)

- `slowapi.wrappers.LimitGroup.__iter__` — direct source inspection, verified callable invocation contract
- `slowapi.extension.Limiter.limit` — direct help() inspection, confirmed `limit_value: Union[str, Callable[..., str]]`
- `grantflow/api/auth.py` — TIER_LIMITS dict, confirmed present and unused
- `grantflow/api/routes.py` — confirmed all static `@limiter.limit("1000/day")` decorators and missing topic param on export
- `grantflow/api/schemas.py` — confirmed `canonical_id` absent from OpportunityResponse
- `grantflow/api/query.py` — confirmed `topic` param exists and filters correctly
- `grantflow/app.py` — confirmed APScheduler pattern, lifespan structure, run_in_executor usage
- `grantflow/enrichment/run_enrichment.py` — confirmed sync function with OPENAI_API_KEY gate
- `grantflow/models.py` — confirmed `canonical_id` column exists on Opportunity model

### Secondary (MEDIUM confidence)

- WebSearch for slowapi dynamic rate limit — confirmed callable support, aligned with source inspection

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed, all patterns already established in codebase
- Architecture: HIGH — implementation patterns verified via direct source code inspection
- Pitfalls: HIGH — identified from direct code analysis (not from documentation or general knowledge)

**Research date:** 2026-03-24
**Valid until:** 2026-06-24 (slowapi 0.1.x API is stable; APScheduler 3.11.x is pinned below 4.0)
