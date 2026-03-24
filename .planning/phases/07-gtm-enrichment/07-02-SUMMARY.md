---
phase: 07-gtm-enrichment
plan: "02"
subsystem: enrichment
tags: [instructor, openai, gpt-4o-mini, topic-tags, search, alembic]

requires:
  - phase: 06-advanced-api-web-ui
    provides: build_opportunity_query, OpportunityResponse, web search page

provides:
  - topic_tags column on opportunities table (migration 0006)
  - grantflow/enrichment/tagger.py — async LLM classification via instructor
  - grantflow/enrichment/run_enrichment.py — CLI batch enrichment entrypoint
  - ?topic= filter on API search endpoint
  - topic dropdown on web search page

affects:
  - 07-gtm-enrichment (plan 07-01 chains Alembic migration 0007 off 0006)
  - any future phase using topic_tags for ML/recommendations

tech-stack:
  added: [instructor, openai]
  patterns:
    - instructor.from_provider("openai", async_client=True) for structured LLM output
    - asyncio.Semaphore(10) for bounded concurrency in batch async calls
    - JSON array string pattern for topic_tags (ilike '%"topic"%' for filter)
    - CLI-only enrichment (no APScheduler) — deferred scheduler wiring pattern

key-files:
  created:
    - grantflow/enrichment/__init__.py
    - grantflow/enrichment/tagger.py
    - grantflow/enrichment/run_enrichment.py
    - alembic/versions/0006_add_topic_tags.py
    - tests/test_enrichment.py
  modified:
    - grantflow/models.py
    - grantflow/api/query.py
    - grantflow/api/routes.py
    - grantflow/api/schemas.py
    - grantflow/web/routes.py
    - templates/search.html
    - tests/test_schemas.py

key-decisions:
  - "topic_tags stored as JSON string TEXT column (not ARRAY) — SQLite-compatible, ilike filter on serialized string works correctly"
  - "instructor.from_provider('openai', async_client=True) — structured output via Pydantic TopicTags model"
  - "Enrichment is CLI-only in Phase 7 — APScheduler integration explicitly deferred until production validation"
  - "asyncio.Semaphore(10) in tag_batch — caps OpenAI concurrency to avoid rate limits"
  - "Commit in sub-batches of 50 — reduces transaction size on large enrichment runs"

patterns-established:
  - "JSON-in-TEXT filter pattern: ilike('%\"topic\"%') matches JSON array string without parsing"
  - "instructor structured output: TopicTags Pydantic model as response_model= ensures type-safe LLM output"
  - "OPENAI_API_KEY gate: check env var at function entry, log and return if absent — safe no-op"

requirements-completed:
  - QUAL-04

duration: 3min
completed: "2026-03-24"
---

# Phase 7 Plan 02: LLM Topic Enrichment Summary

**Async instructor + gpt-4o-mini topic classification with ilike JSON filter on API search and web dropdown, gated on OPENAI_API_KEY, CLI-only for Phase 7**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-24T20:22:09Z
- **Completed:** 2026-03-24T20:25:32Z
- **Tasks:** 1 (TDD: test commit + implementation commit)
- **Files modified:** 12

## Accomplishments

- topic_tags TEXT column added to opportunities via Alembic migration 0006
- Enrichment module with instructor + OpenAI gpt-4o-mini: tag_single (single async call) and tag_batch (bounded concurrency via Semaphore(10))
- run_enrichment() CLI entrypoint: skips when OPENAI_API_KEY unset, caps at ENRICHMENT_BATCH_SIZE (default 500), commits in sub-batches of 50
- API search endpoint accepts ?topic= filter using ilike on JSON array string
- Web search page has topic dropdown with all 13 topic categories
- All 175 tests pass (5 new enrichment tests + 170 existing)

## Task Commits

TDD flow — two commits for the single task:

1. **RED: failing tests** - `eb8cb88` (test)
2. **GREEN + implementation** - `b3abb92` (feat)

**Plan metadata:** (docs commit — created after this summary)

## Files Created/Modified

- `grantflow/enrichment/__init__.py` — empty package marker
- `grantflow/enrichment/tagger.py` — TopicTags Pydantic model, tag_single/tag_batch async functions
- `grantflow/enrichment/run_enrichment.py` — CLI entrypoint with OPENAI_API_KEY gate and batch cap
- `alembic/versions/0006_add_topic_tags.py` — ADD COLUMN topic_tags TEXT (revision 0006, down_revision 0005)
- `grantflow/models.py` — topic_tags = Column(Text, nullable=True) added to Opportunity
- `grantflow/api/query.py` — topic parameter added to build_opportunity_query() with ilike filter
- `grantflow/api/routes.py` — topic: str | None = Query(None) added to search endpoint
- `grantflow/api/schemas.py` — topic_tags: Optional[str] = None added to OpportunityResponse
- `grantflow/web/routes.py` — topic parameter added to search_page() and _build_filters()
- `templates/search.html` — topic dropdown with 13 categories added to filter row
- `tests/test_enrichment.py` — 5 new tests (mock LLM, filter, excludes, skip, batch limit)
- `tests/test_schemas.py` — expected_keys updated to include topic_tags

## Decisions Made

- topic_tags stored as JSON array string in TEXT column — SQLite-compatible and ilike filter (`'%"health"%'`) correctly matches JSON without parsing overhead
- instructor.from_provider("openai", async_client=True) pattern — structured output via Pydantic avoids manual JSON parsing of LLM responses
- APScheduler wiring deferred — enrichment validated via CLI first before embedding in scheduler
- Semaphore(10) on batch concurrency — prevents OpenAI 429 rate limit hits on large batches

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_schemas.py expected_keys set outdated after schema extension**
- **Found during:** Task 1 (full suite regression run)
- **Issue:** `test_opportunity_response_preserves_exact_field_names` hardcoded expected field set without `topic_tags`; failed after OpportunityResponse gained the new field
- **Fix:** Added `"topic_tags"` to the expected_keys set in test_schemas.py
- **Files modified:** `tests/test_schemas.py`
- **Verification:** Full suite passes (175 passed)
- **Committed in:** b3abb92 (part of feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — pre-existing test required update for schema change)
**Impact on plan:** Necessary correctness fix. No scope creep.

## Issues Encountered

- Stale `test_grantflow.db` missing `search_vector` column caused OperationalError in `test_enrichment_batch_limit` — deleted and let conftest recreate via `Base.metadata.create_all()`

## User Setup Required

To run enrichment:
```bash
export OPENAI_API_KEY=sk-...
export ENRICHMENT_BATCH_SIZE=500  # optional, default 500
uv run python -m grantflow.enrichment.run_enrichment
```

## Next Phase Readiness

- Alembic migration 0006 is committed; plan 07-01 (Wave 2) can chain migration 0007 off it
- topic_tags column is live in schema, ready for enrichment runs
- Enrichment is CLI-only; APScheduler integration deferred to a future phase

---
*Phase: 07-gtm-enrichment*
*Completed: 2026-03-24*
