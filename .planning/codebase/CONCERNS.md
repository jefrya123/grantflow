# Codebase Concerns

**Analysis Date:** 2026-03-24

## Tech Debt

**Duplicated search logic between API and web routes:**
- Issue: Full search/filter/sort logic is copy-pasted nearly verbatim across two files. Any bug fix or new filter must be applied twice.
- Files: `grantflow/api/routes.py` (lines 30–94), `grantflow/web/routes.py` (lines 41–110)
- Impact: Filters present in the API (`eligible`, `category`) are absent from the allowed sort fields in the web route. Divergence will grow over time.
- Fix approach: Extract a shared `build_opportunity_query(db, filters)` helper in a new `grantflow/queries.py` module; both routes call it.

**`_opportunity_to_dict` serializer is manual and redundant:**
- Issue: Hand-rolled dict serializer lists every field explicitly. Pydantic response models exist in the stack (FastAPI + Pydantic 2) but are not used.
- Files: `grantflow/api/routes.py` lines 185–212
- Impact: New model fields added to `grantflow/models.py` will silently be missing from API responses.
- Fix approach: Define a `OpportunityResponse` Pydantic model with `model_config = ConfigDict(from_attributes=True)` and use it as the response model.

**`updated_at` column never updated on Opportunity model:**
- Issue: `updated_at` has a `default=` factory but no `onupdate=` SQLAlchemy event. All upserts set `updated_at` manually only via `record["updated_at"] = now_iso` in `grants_gov.py`, but not in `sbir.py` or `usaspending.py`.
- Files: `grantflow/models.py` line 40, `grantflow/ingest/sbir.py` lines 148–151, `grantflow/ingest/usaspending.py` lines 155–157
- Impact: `updated_at` is stale/wrong for SBIR and USAspending upserts.
- Fix approach: Add `onupdate=lambda: datetime.now(timezone.utc).isoformat()` to the column definition, or unify via an `onupdate` SQLAlchemy `Column` parameter.

**FTS index rebuilt redundantly and inconsistently:**
- Issue: `ingest_grants_gov()` rebuilds the FTS index at the end of its own run (lines 238–244), and `run_all.py` also calls `_rebuild_fts()` after all sources complete. The grants_gov rebuild is redundant and rebuilds before SBIR/USAspending records are inserted.
- Files: `grantflow/ingest/grants_gov.py` lines 237–244, `grantflow/ingest/run_all.py` lines 17–27
- Fix approach: Remove the FTS rebuild from `ingest_grants_gov()` and rely solely on the final rebuild in `run_all.py`.

**`hashlib` imported inside a hot loop:**
- Issue: `import hashlib` is placed inside `_make_award_key()` which is called per-row during CSV processing (potentially hundreds of thousands of rows).
- Files: `grantflow/ingest/sbir.py` line 58
- Fix approach: Move `import hashlib` to the top of the file.

**`from fastapi import HTTPException` imported inside a function:**
- Issue: Import is deferred inside `detail_page()` rather than at module level.
- Files: `grantflow/web/routes.py` line 120
- Fix approach: Move to top-level imports.

**`from sqlalchemy import text` imported inside a function:**
- Issue: Same pattern — deferred import inside `search_page()`.
- Files: `grantflow/web/routes.py` line 39
- Fix approach: Move to top-level imports.

**Agency code generation is lossy and non-deterministic:**
- Issue: Agency codes are derived by `agency_name.replace(" ", "_").upper()[:50]`, which truncates at 50 chars and can collide for agencies whose names share the same first 50 characters. No uniqueness check.
- Files: `grantflow/ingest/usaspending.py` lines 178–184
- Impact: Silently drops agencies on collision; the `agencies` table is populated but never used by queries.
- Fix approach: Use a proper slug or the actual agency code field from USAspending responses.

---

## Known Bugs

**FTS search returns wrong rowids when combined with filters:**
- Symptoms: When `q` is provided along with filters (status, agency, etc.), the query filters on `opportunities.rowid IN (...)` using a raw text interpolation, then applies ORM filters. The rowid list is interpolated directly into SQL (f-string), making it fragile if rowids are non-integer.
- Files: `grantflow/api/routes.py` lines 32–41, `grantflow/web/routes.py` lines 43–63
- Trigger: Any full-text search combined with additional filters.
- Workaround: None; generally works for integer rowids in SQLite but is not parameterized.

**Pagination `pages` calculation always returns at least 1 even with 0 results:**
- Symptoms: When total=0, `pages = max(1, ...)` returns 1, so the pagination block renders a single empty page. The FTS early-return path (lines 37–39 in api/routes.py) correctly returns `pages: 0`, but the non-FTS path does not.
- Files: `grantflow/api/routes.py` line 84, `grantflow/web/routes.py` line 98
- Fix approach: Use `pages = (total + per_page - 1) // per_page` without the `max(1, ...)` wrapper; return 0 for empty result sets.

**SBIR solicitation `opportunity_status` is never set:**
- Symptoms: All SBIR solicitations ingested as opportunities have `NULL` for `opportunity_status`, so filtering by `status=posted` won't find them.
- Files: `grantflow/ingest/sbir.py` lines 205–220 — `record` dict has no `opportunity_status` key
- Fix approach: Derive status from `close_date` vs. today, or default to `"posted"` for newly fetched solicitations.

**`closing_after` / `closing_before` filters accept unchecked strings:**
- Symptoms: Date parameters are passed directly into SQLAlchemy filter comparisons against TEXT columns with no format validation. Malformed input produces silent query mismatches rather than errors.
- Files: `grantflow/api/routes.py` lines 60–63, `grantflow/web/routes.py` lines 79–82
- Fix approach: Validate via `datetime.strptime(value, "%Y-%m-%d")` and raise HTTP 422 on failure.

---

## Security Considerations

**Wildcard CORS policy:**
- Risk: `allow_origins=["*"]` combined with `allow_credentials=True` is rejected by browsers (CORS spec forbids wildcard + credentials), but signals no CORS thought has been applied.
- Files: `grantflow/app.py` lines 24–29
- Current mitigation: None.
- Recommendations: Set `allow_origins` to an explicit list of trusted origins; remove `allow_credentials=True` if not using cookies/auth.

**FTS rowid list interpolated directly into SQL:**
- Risk: The rowid list from FTS is joined into an f-string SQL fragment without parameterization: `f"opportunities.rowid IN ({','.join(str(r) for r in rowids)})"`. While rowids come from SQLite's own FTS engine (not user input), this pattern normalizes raw SQL construction.
- Files: `grantflow/api/routes.py` line 40, `grantflow/web/routes.py` line 62
- Current mitigation: Input originates from the database, not directly from user.
- Recommendations: Use SQLAlchemy's `Opportunity.rowid.in_(rowids)` or bind the list via `bindparam` to stay entirely parameterized.

**`contact_email` rendered as `mailto:` href without validation:**
- Risk: `opp.contact_email` from raw external data is rendered directly as `<a href="mailto:{{ opp.contact_email }}">`. A malicious `javascript:` value in source data could become an XSS vector; Jinja2 auto-escaping handles HTML but not URI schemes in `href`.
- Files: `templates/detail.html` line 97
- Current mitigation: Jinja2 HTML escapes the value, preventing `<script>` injection but not `javascript:` URIs.
- Recommendations: Validate email format before storage during ingestion, or add a Jinja2 filter to strip non-`mailto:` prefixes.

**`opp.description` rendered unescaped in detail template:**
- Risk: Description content comes from external federal APIs and is rendered as `{{ opp.description }}` inside a `<div class="description-text">`. Jinja2 auto-escaping is on by default for `.html` files, so this is likely safe — but descriptions may contain encoded HTML that renders as raw markup if `| safe` is ever added.
- Files: `templates/detail.html` line 89
- Current mitigation: Jinja2 auto-escaping active.
- Recommendations: No immediate action; document that `| safe` must never be applied to `description`.

**Server IP exposed in plan.md:**
- Risk: `plan.md` contains the production VPS IP address (`5.161.92.74`) and deployment target details committed to the repository.
- Files: `plan.md` line 241
- Current mitigation: `.gitignore` does not exclude `plan.md`.
- Recommendations: Remove the IP from `plan.md` or move deployment details to a private document not committed to the repo.

---

## Performance Bottlenecks

**N+1 lookup in `_upsert_batch` (grants_gov):**
- Problem: Each record in a batch of 500 calls `session.get(Opportunity, opp_id)` individually — 500 separate SELECT queries per batch, potentially hundreds of thousands of queries for a full XML parse.
- Files: `grantflow/ingest/grants_gov.py` lines 278–290
- Cause: Individual ORM `get()` calls instead of bulk existence check.
- Improvement path: Pre-fetch all existing IDs in the batch with one `SELECT id FROM opportunities WHERE id IN (...)`, then partition the batch into inserts vs. updates.

**Same N+1 pattern in SBIR and USAspending upserts:**
- Problem: Both ingesters call `session.get(Award, record_id)` per row inside their main loops.
- Files: `grantflow/ingest/sbir.py` lines 147–156, `grantflow/ingest/usaspending.py` lines 153–162
- Improvement path: Same bulk pre-fetch approach as above.

**Full `query.count()` before pagination on every search request:**
- Problem: Each search fires a `COUNT(*)` query followed by the paged SELECT. For large result sets with complex FTS + filter combinations, the count query is expensive and repeated on every page navigation.
- Files: `grantflow/api/routes.py` line 66, `grantflow/web/routes.py` line 84
- Cause: No caching of count results.
- Improvement path: Accept approximate counts, cache count per filter combination, or drop total count display in favor of "has next page" signals.

**SBIR CSV loaded entirely into Python per ingest run (~290 MB):**
- Problem: The full CSV is re-read line by line on every ingest run. There is no incremental loading — all rows are processed and upserted regardless of whether they changed.
- Files: `grantflow/ingest/sbir.py` lines 86–163
- Cause: No checksum or last-modified tracking.
- Improvement path: Track file mtime or ETag; skip rows whose award key already exists and whose data hasn't changed.

**Awards link lookup uses `ilike` on unbounded text columns:**
- Problem: `Award.cfda_numbers.ilike(f"%{opp.cfda_numbers}%")` on the detail page performs a full table scan with a leading wildcard pattern, which cannot use any index.
- Files: `grantflow/api/routes.py` lines 111–114, `grantflow/web/routes.py` lines 130–134
- Improvement path: Normalize CFDA numbers into a separate linking table, or at minimum store them in a format amenable to indexed prefix matching.

---

## Fragile Areas

**FTS content table is an external-content FTS5 table:**
- Files: `grantflow/database.py` lines 38–44
- Why fragile: SQLite FTS5 external-content tables do not auto-update when the source table changes. Any direct insert/update to `opportunities` that bypasses the explicit FTS rebuild leaves the index stale. The rebuild is manual and only happens after full ingestion runs.
- Safe modification: Always call `_rebuild_fts()` after any write to `opportunities`, or switch to a trigger-based approach.
- Test coverage: None — no tests verify FTS index freshness.

**Ingestion scripts use module-level `SessionLocal()` without the FastAPI dependency injection system:**
- Files: `grantflow/ingest/grants_gov.py` line 165, `grantflow/ingest/sbir.py` line 249, `grantflow/ingest/usaspending.py` line 110
- Why fragile: Sessions are created directly and managed manually. A future refactor that changes `DATABASE_URL` or connection settings could leave ingest scripts using a different engine than the API.
- Safe modification: Share a single `engine` and `SessionLocal` factory from `grantflow/database.py` (already done), but also pass the session as a parameter to allow testing with a test database.

**`_find_extract_url` in grants_gov relies on date-based URL guessing:**
- Files: `grantflow/ingest/grants_gov.py` lines 66–97
- Why fragile: Tries up to 21 URL variants (7 days × 3 versions) via HTTP HEAD requests before falling back to HTML scraping. If Grants.gov changes file naming conventions or S3 bucket structure, all 21 attempts will fail and the scrape fallback will also break silently.
- Safe modification: Add an alerting path when all URL patterns fail; log the full set of tried URLs.

**`order` query parameter has no allowlist enforcement:**
- Files: `grantflow/api/routes.py` line 78, `grantflow/web/routes.py` line 93
- Why fragile: `order` can be any string; only `"asc"` triggers ascending — everything else silently defaults to descending. This is safe but can surprise callers passing invalid values.
- Safe modification: Validate `order` is one of `{"asc", "desc"}` and raise HTTP 422 otherwise.

---

## Scaling Limits

**SQLite as the sole database:**
- Current capacity: Suitable for read-heavy single-server workloads with WAL mode enabled. Writes are serialized.
- Limit: Concurrent write ingestion from multiple processes will queue behind the WAL lock. Full ingestion runs (potentially millions of rows) block reads during flush operations.
- Scaling path: Migrate to PostgreSQL when concurrent writes or multi-process ingestion is needed. SQLAlchemy models are compatible; only `DATABASE_URL` and FTS (use `pg_trgm` or `tsvector`) would change.

**USAspending hard cap at 5,000 records:**
- Current capacity: `MAX_RECORDS = 5000` in `grantflow/ingest/usaspending.py` line 38
- Limit: The last 2 years of federal grant awards far exceeds 5,000 records; the cap means only the highest-dollar awards are captured.
- Scaling path: Increase `MAX_RECORDS`, paginate more aggressively, or filter by specific agencies/CFDA numbers to get complete coverage within a bounded scope.

---

## Missing Critical Features

**No scheduled/automated ingestion:**
- Problem: There is no cron job, systemd timer, or task queue to run `run_all.py` automatically. Data goes stale immediately after deployment.
- Blocks: The core value proposition (fresh daily grant data) depends on this.

**No tests:**
- Problem: The `tests/` directory exists but is empty. There are no unit tests, integration tests, or API tests of any kind.
- Blocks: Any refactoring or new feature addition carries unquantified regression risk.
- Priority: High

**No health check or ingestion status endpoint:**
- Problem: No API endpoint exposes when data was last ingested or whether the last run succeeded. The `ingestion_log` table exists but is not surfaced via the API.
- Blocks: Operators cannot tell if the data pipeline is healthy without querying the database directly.

---

## Test Coverage Gaps

**No tests exist at all:**
- What's not tested: All search logic, FTS query construction, pagination math, ingest parsing, date normalization, award linking, API response shapes.
- Files: Entire `grantflow/` package
- Risk: Silent regressions in date parsing, filter logic, or FTS behavior will not be caught.
- Priority: High

**Date normalization has multiple format branches with no tests:**
- What's not tested: `_normalize_date()` in `grantflow/ingest/grants_gov.py` (lines 54–63) and `_parse_date()` in `grantflow/ingest/sbir.py` (lines 35–45) handle 3–4 date formats each. Edge cases (empty string, partial dates, malformed values) fall through silently to returning the raw value.
- Files: `grantflow/ingest/grants_gov.py`, `grantflow/ingest/sbir.py`
- Risk: Malformed dates stored as TEXT will sort incorrectly and break date range filters.
- Priority: Medium

---

*Concerns audit: 2026-03-24*
