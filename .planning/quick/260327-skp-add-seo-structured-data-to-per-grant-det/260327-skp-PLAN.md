---
phase: quick
plan: 260327-skp
type: execute
wave: 1
depends_on: []
files_modified:
  - templates/detail.html
  - tests/test_web_ui.py
autonomous: true
requirements: [SEO-detail-page]
must_haves:
  truths:
    - "Opportunity detail page includes JSON-LD structured data with grant title, description, funder, dates, and amount"
    - "Opportunity detail page includes Open Graph meta tags for social sharing"
    - "Opportunity detail page includes Twitter Card meta tags"
    - "Tests verify JSON-LD and OG tags appear in response HTML"
  artifacts:
    - path: "templates/detail.html"
      provides: "JSON-LD, OG, and Twitter Card meta tags in head_extra block"
      contains: "application/ld+json"
    - path: "tests/test_web_ui.py"
      provides: "SEO meta tag tests for detail page"
      contains: "test_detail_seo"
  key_links:
    - from: "templates/detail.html"
      to: "routes.py detail_page context"
      via: "opp template variable"
      pattern: "opp\\.title|opp\\.description|opp\\.agency_name"
---

<objective>
Add SEO structured data (JSON-LD, Open Graph, Twitter Card) to the per-grant opportunity detail page at `/opportunity/{id}`.

Purpose: Improve search engine discoverability and social sharing appearance for individual grant pages.
Output: Updated detail.html template with structured data; tests proving it works.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@templates/agency.html (reference pattern — has working JSON-LD + OG implementation)
@templates/detail.html (target file — currently has NO head_extra block)
@templates/base.html (defines {% block head_extra %})
@grantflow/web/routes.py (detail_page route passes `opp` and `awards` to template)

<interfaces>
<!-- The detail_page route (line 131-154 of routes.py) passes these context vars: -->
<!-- opp: Opportunity ORM object, awards: list[Award] -->

<!-- Key Opportunity fields available in template (from models.py): -->
<!-- opp.id, opp.title, opp.description, opp.agency_name, opp.agency_code -->
<!-- opp.post_date, opp.close_date, opp.award_floor, opp.award_ceiling -->
<!-- opp.opportunity_number, opp.source_url, opp.opportunity_status -->

<!-- Test fixtures use: client (TestClient), db_session (SQLAlchemy session) -->
<!-- Helper pattern: _make_opp(db_session, id=..., title=..., **kwargs) -->
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add JSON-LD, OG, and Twitter Card structured data to detail.html</name>
  <files>templates/detail.html</files>
  <behavior>
    - Test 1: GET /opportunity/{id} response contains 'application/ld+json' script tag
    - Test 2: JSON-LD contains GovernmentService @type with grant title and description
    - Test 3: Response contains og:title, og:description, og:type, og:url meta tags
    - Test 4: Response contains twitter:card meta tag
  </behavior>
  <action>
Add a `{% block head_extra %}` section to `templates/detail.html` between the `{% block title %}` line and `{% block content %}`. Follow the exact pattern from `templates/agency.html`.

Include these elements:

1. **meta description tag:**
   ```html
   <meta name="description" content="{{ opp.description[:160] if opp.description else opp.title }} - Federal grant opportunity on GrantFlow">
   ```

2. **Open Graph tags:**
   ```html
   <meta property="og:title" content="{{ opp.title }} - GrantFlow">
   <meta property="og:description" content="{{ opp.description[:200] if opp.description else 'Federal grant opportunity' }}">
   <meta property="og:type" content="website">
   <meta property="og:url" content="{{ request.url }}">
   ```

3. **Twitter Card tags:**
   ```html
   <meta name="twitter:card" content="summary">
   <meta name="twitter:title" content="{{ opp.title }} - GrantFlow">
   <meta name="twitter:description" content="{{ opp.description[:200] if opp.description else 'Federal grant opportunity' }}">
   ```

4. **JSON-LD structured data** using `GovernmentService` type:
   ```html
   <script type="application/ld+json">
   {
     "@context": "https://schema.org",
     "@type": "GovernmentService",
     "name": "{{ opp.title }}",
     {% if opp.description %}"description": "{{ opp.description[:500]|e }}",{% endif %}
     {% if opp.agency_name %}"serviceOperator": {
       "@type": "GovernmentOrganization",
       "name": "{{ opp.agency_name }}"
     },{% endif %}
     {% if opp.close_date %}"areaServed": "US"{% endif %}
   }
   </script>
   ```

Note: The route already passes `request` to `TemplateResponse` (line 151), so `request.url` is available. Escape description content with `|e` Jinja filter in JSON-LD to prevent JSON breakage from quotes/special chars.
  </action>
  <verify>
    <automated>cd ~/Projects/grantflow && uv run pytest tests/test_web_ui.py -x -q --tb=short -k "detail"</automated>
  </verify>
  <done>detail.html has head_extra block with JSON-LD (GovernmentService), OG tags (title, description, type, url), and Twitter Card tags. All existing detail tests still pass.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Write tests for detail page SEO structured data</name>
  <files>tests/test_web_ui.py</files>
  <behavior>
    - test_detail_seo_jsonld: GET /opportunity/{id} contains 'application/ld+json' and 'GovernmentService'
    - test_detail_seo_og_tags: response contains og:title, og:description, og:type
    - test_detail_seo_twitter_card: response contains twitter:card
    - test_detail_seo_includes_agency: JSON-LD contains agency name when present
  </behavior>
  <action>
Add a new test section to `tests/test_web_ui.py` after the existing detail page tests (after `test_detail_no_awards_section` around line 134). Use the existing `_make_opp` helper.

Add these tests:

```python
# ---------------------------------------------------------------------------
# WEB-05: Detail page SEO structured data
# ---------------------------------------------------------------------------

def test_detail_seo_jsonld(client, db_session):
    """Detail page includes JSON-LD structured data with GovernmentService type."""
    _make_opp(db_session, id="seo-opp-1", title="SEO Test Grant",
              description="A grant for testing SEO structured data",
              agency_name="Dept of Energy", agency_code="DOE",
              opportunity_number="SEO-001")

    response = client.get("/opportunity/seo-opp-1")
    assert response.status_code == 200
    html = response.text
    assert 'application/ld+json' in html
    assert 'GovernmentService' in html
    assert 'SEO Test Grant' in html


def test_detail_seo_og_tags(client, db_session):
    """Detail page includes Open Graph meta tags."""
    _make_opp(db_session, id="seo-opp-2", title="OG Test Grant",
              description="Grant for OG tag testing",
              opportunity_number="SEO-002")

    response = client.get("/opportunity/seo-opp-2")
    assert response.status_code == 200
    html = response.text
    assert 'og:title' in html
    assert 'og:description' in html
    assert 'og:type' in html
    assert 'OG Test Grant' in html


def test_detail_seo_twitter_card(client, db_session):
    """Detail page includes Twitter Card meta tags."""
    _make_opp(db_session, id="seo-opp-3", title="Twitter Test Grant",
              opportunity_number="SEO-003")

    response = client.get("/opportunity/seo-opp-3")
    assert response.status_code == 200
    html = response.text
    assert 'twitter:card' in html
    assert 'twitter:title' in html


def test_detail_seo_includes_agency(client, db_session):
    """JSON-LD includes agency as serviceOperator when present."""
    _make_opp(db_session, id="seo-opp-4", title="Agency SEO Grant",
              agency_name="National Science Foundation",
              opportunity_number="SEO-004")

    response = client.get("/opportunity/seo-opp-4")
    assert response.status_code == 200
    html = response.text
    assert 'National Science Foundation' in html
    assert 'GovernmentOrganization' in html
```

Place after line ~134 (after `test_detail_no_awards_section`). Ensure unique `id` and `opportunity_number` values to avoid conflicts with existing test data.
  </action>
  <verify>
    <automated>cd ~/Projects/grantflow && uv run pytest tests/test_web_ui.py -x -q --tb=short -k "seo"</automated>
  </verify>
  <done>Four SEO tests pass: JSON-LD present with GovernmentService, OG tags present, Twitter Card present, agency in serviceOperator.</done>
</task>

</tasks>

<verification>
```bash
cd ~/Projects/grantflow && uv run pytest tests/test_web_ui.py tests/test_agency_page.py -x -q --tb=short
```
All existing tests pass plus new SEO tests.

```bash
cd ~/Projects/grantflow && uv run ruff check . --fix && uv run ruff format . && uv run mypy grantflow/ && uv run pytest --tb=short -q
```
Full quality gates pass.
</verification>

<success_criteria>
- detail.html has {% block head_extra %} with JSON-LD (GovernmentService schema), OG tags, and Twitter Card tags
- JSON-LD includes grant title, description, and agency (when available)
- OG tags include og:title, og:description, og:type, og:url
- Twitter Card tags include twitter:card and twitter:title
- 4 new tests in test_web_ui.py all pass
- All existing tests continue to pass
- Full quality gates pass (ruff, mypy, pytest)
</success_criteria>

<output>
After completion:
1. Run quality gates: `cd ~/Projects/grantflow && uv run ruff check . --fix && uv run ruff format . && uv run mypy grantflow/ && uv run pytest --tb=short -q`
2. Commit: `cd ~/Projects/grantflow && git add -A && git commit -m 'ceo: SEO structured data for per-grant pages' && git push origin main`
3. Check off in playbook: `[x] SEO: per-grant pages (structured data on detail page)` in `~/Projects/projects-ceo/playbooks/grantflow.md`
</output>
