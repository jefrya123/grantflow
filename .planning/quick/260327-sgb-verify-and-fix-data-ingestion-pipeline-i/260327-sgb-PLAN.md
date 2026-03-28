---
phase: 260327-sgb
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - grantflow/ingest/state/colorado.py
  - tests/test_pipeline_imports.py
  - playbooks/grantflow.md
autonomous: true
requirements: []
must_haves:
  truths:
    - "Federal pipeline (run_all.py) imports and initializes without errors"
    - "State pipeline (run_state.py) imports and initializes without errors"
    - "APScheduler starts and registers all 3 jobs without errors"
    - "Colorado scraper returns > 1 record (or explicitly marks as skipped/degraded)"
    - "All 228+ tests pass with no new failures"
  artifacts:
    - path: "grantflow/ingest/state/colorado.py"
      provides: "Colorado scraper with improved record extraction or degraded-mode fallback"
    - path: "tests/test_pipeline_imports.py"
      provides: "Smoke tests covering import, initialization, and Colorado normalize_record"
  key_links:
    - from: "grantflow/app.py"
      to: "grantflow/ingest/run_all.py"
      via: "import at module level"
    - from: "grantflow/ingest/run_state.py"
      to: "grantflow/ingest/state/colorado.py"
      via: "_get_scrapers()"
---

<objective>
Verify the data ingestion pipeline works end-to-end: federal sources, state scrapers, APScheduler
wiring, and the pipeline_runs table. Fix the Colorado scraper which is known to return only 1 record
(portal structure likely changed). Write a smoke test verifying import + initialization, then run
quality gates and commit.

Purpose: Ensure the overnight CEO can rely on grantflow ingestion producing real data, not silent 1-record runs.
Output: Fixed Colorado scraper, passing smoke tests, clean quality gates, committed code, playbook checkbox updated.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
Project root: /home/jeff/Projects/grantflow

## Current state (verified before planning)

- `uv run pytest` passes: 228 passed, 1 xpassed (0 failures)
- `from grantflow.ingest.run_all import run_all_ingestion` imports cleanly with `uv run`
- `from grantflow.ingest.run_state import run_state_ingestion` imports cleanly
- APScheduler configured in `grantflow/app.py` lines 14-82: 3 jobs registered
  (run_all_ingestion daily 02:00 UTC, run_state_ingestion Sunday 03:00 UTC, enrichment 04:00 UTC)
- `tests/test_pipeline_imports.py` already has 5 smoke tests — all passing
- `pipeline_runs` table shows Colorado returning 1 record (last run 2026-03-24)
  while other states return hundreds–thousands
- Colorado scraper (`grantflow/ingest/state/colorado.py`) scrapes `choosecolorado.com`
  HTML — portal structure likely changed (only 1 record extracted)

## Colorado scraper behavior

The scraper tries:
1. `table tbody tr` rows (structured table)
2. Fallback: `ul.grants-list li`, `.grant-item`, `article`, `.entry-content li`

If neither finds records it logs a warning and returns []. The 1-record result means one
of the fallback selectors matched a single element. This is a live-scraping issue —
the portal page structure has changed. Fix: add a more defensive fallback that logs
clearly when only 0–2 records are found and marks status as "degraded" instead of "success".
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Fix Colorado scraper low-record detection and add degraded status</name>
  <files>grantflow/ingest/state/colorado.py, tests/test_pipeline_imports.py</files>
  <behavior>
    - Test: ColoradoScraper.run() returns dict with status="degraded" when fetch_records returns 0-2 records
    - Test: ColoradoScraper.normalize_record() with valid title returns dict with all required keys
    - Test: ColoradoScraper.normalize_record() with empty title returns None
    - Existing test_colorado_normalize_record_returns_expected_keys must still pass
  </behavior>
  <action>
    FIRST: Write failing tests in tests/test_pipeline_imports.py (append, don't replace):

    ```python
    def test_colorado_run_returns_degraded_on_too_few_records(monkeypatch) -> None:
        """ColoradoScraper.run() returns status='degraded' when < 3 real records found."""
        from grantflow.ingest.state.colorado import ColoradoScraper

        scraper = ColoradoScraper()
        # Simulate fetch_records returning 1 item (portal broken)
        monkeypatch.setattr(scraper, "fetch_records", lambda: [
            {"title": "Only Grant", "agency": "CO", "deadline": "", "url": ""}
        ])
        result = scraper.run()
        assert result["status"] == "degraded"
        assert result.get("records_processed", 0) <= 2

    def test_colorado_normalize_record_returns_none_on_empty_title() -> None:
        """normalize_record returns None when title is empty/missing."""
        from grantflow.ingest.state.colorado import ColoradoScraper

        scraper = ColoradoScraper()
        assert scraper.normalize_record({"title": "", "agency": "CO"}) is None
        assert scraper.normalize_record({"agency": "CO"}) is None
    ```

    Run tests — they MUST fail before implementation.

    THEN: Update `grantflow/ingest/state/colorado.py` BaseStateScraper.run() override:
    - If `fetch_records()` returns fewer than 3 records, set status to "degraded" with
      a clear log warning: "colorado_too_few_records", count=N, threshold=3
    - Return result dict with status="degraded", records_processed=N, records_added=0,
      error="Too few records ({N}) — portal structure may have changed"

    Check if BaseStateScraper has a `run()` method first:
    ```bash
    grep -n "def run" /home/jeff/Projects/grantflow/grantflow/ingest/state/base.py
    ```
    If base has run(): override it in ColoradoScraper. If not: add run() to ColoradoScraper
    that calls fetch_records(), checks count, and delegates to super() or implements inline.

    The normalize_record None-on-empty-title behavior is already implemented (line 121:
    `if not title: return None`) — the test just needs to confirm it. No code change needed there.

    Run tests again — all must pass.
  </action>
  <verify>
    <automated>cd /home/jeff/Projects/grantflow && uv run pytest tests/test_pipeline_imports.py -v 2>&1</automated>
  </verify>
  <done>
    test_pipeline_imports.py has 7+ tests, all passing. ColoradoScraper returns
    status="degraded" when fetch_records returns fewer than 3 records.
  </done>
</task>

<task type="auto">
  <name>Task 2: Quality gates, commit, and playbook update</name>
  <files>/home/jeff/Projects/projects-ceo/playbooks/grantflow.md</files>
  <action>
    Run quality gates in order — all must pass before commit:

    ```bash
    cd /home/jeff/Projects/grantflow
    uv run ruff check . --fix && uv run ruff format . && uv run ruff check .
    uv run mypy grantflow/ --ignore-missing-imports
    uv run pytest --tb=short -q
    ```

    If ruff or mypy finds issues in the files modified in Task 1, fix them before proceeding.
    Common mypy issues: missing return type annotations, Optional handling. Add type hints as needed.

    Once all pass, commit:
    ```bash
    cd /home/jeff/Projects/grantflow
    git add grantflow/ingest/state/colorado.py tests/test_pipeline_imports.py
    git commit -m "ceo: verify and fix data ingestion pipeline"
    git push origin main
    ```

    Then check off the playbook item:
    ```bash
    # In /home/jeff/Projects/projects-ceo/playbooks/grantflow.md
    # Find line: [ ] Verify data ingestion pipeline works end-to-end
    # Change to: [x] Verify data ingestion pipeline works end-to-end (2026-03-27)
    ```
    Use Edit tool to update the checkbox in playbooks/grantflow.md.
  </action>
  <verify>
    <automated>cd /home/jeff/Projects/grantflow && uv run pytest --tb=short -q 2>&1 | tail -5</automated>
  </verify>
  <done>
    All tests pass (228+ passed, 0 failed). Commit exists with message
    "ceo: verify and fix data ingestion pipeline". Playbook checkbox marked [x].
  </done>
</task>

</tasks>

<verification>
After both tasks complete, verify end state:

```bash
cd /home/jeff/Projects/grantflow
uv run pytest tests/test_pipeline_imports.py -v
git log --oneline -3
```

Expected: 7+ pipeline import tests passing, commit visible in log.

```bash
grep "Verify data ingestion pipeline" /home/jeff/Projects/projects-ceo/playbooks/grantflow.md
```

Expected: Line shows `[x]` checkbox.
</verification>

<success_criteria>
- All existing 228 tests still pass (no regressions)
- test_pipeline_imports.py has new tests for Colorado degraded status and empty-title normalization
- Colorado scraper correctly flags low-record runs as "degraded" not "success"
- ruff + mypy pass with no errors
- Commit "ceo: verify and fix data ingestion pipeline" pushed to origin main
- Playbook checkbox `[x] Verify data ingestion pipeline works end-to-end` marked done
</success_criteria>

<output>
After completion, create `/home/jeff/Projects/grantflow/.planning/quick/260327-sgb-verify-and-fix-data-ingestion-pipeline-i/260327-sgb-SUMMARY.md`
</output>
