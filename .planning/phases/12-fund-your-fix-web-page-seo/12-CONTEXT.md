# Phase 12: Fund Your Fix Web Page & SEO - Context

**Gathered:** 2026-03-29
**Status:** Ready for planning
**Mode:** Smart discuss (autonomous)

<domain>
## Phase Boundary

Complete the /fund-your-fix page and its supporting infrastructure: add municipality filter to the web route, pin DOT FTA "All Stations Access" as the featured grant, add /ada-grants redirect, add an embeddable widget endpoint at /fund-your-fix/widget, add og:image to the template, and write tests for all new functionality.

</domain>

<decisions>
## Implementation Decisions

### Municipality Filter (Web Page)
- Same fail-open logic as API: ilike match on eligible_applicants + description, fallback to all ADA grants
- Show `Showing grants for: {municipality}` banner in template when municipality param is set
- Pass `municipality` variable to template context
- Template shows the filter banner only when municipality is non-empty

### Featured Grant Pinning
- Query for "All Stations Access" by title ilike `%all stations%` first; fall back to soonest-closing
- Highlight with red/urgent styling when close_date is 2026-05-01 (or within 60 days)
- Pass `featured_is_fta` boolean to template to enable special styling

### Widget Endpoint
- HTML fragment at `/fund-your-fix/widget` — no full page chrome, iframeable by ada-audit
- Returns top 5 ADA grants with title, deadline, award, and link to full page
- Public, no API key required
- CORS-permissive (inherits from global CORS config)

### SEO / Meta
- Add `og:image` meta tag pointing to `/static/og-fund-your-fix.png` (browsers degrade gracefully if file absent)
- /ada-grants redirects 301 to /fund-your-fix

### Claude's Discretion
- Widget template styling: match existing site color palette (inline styles, no separate CSS)
- Test data: use existing _make_ada_opp helper pattern from test_fund_your_fix.py

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/test_fund_your_fix.py` — `_make_ada_opp()` helper, existing test fixtures
- `grantflow/web/routes.py` — `fund_your_fix_page()` route pattern to extend
- `templates/fund_your_fix.html` — existing template to update
- `templates/base.html` — base template with `head_extra` block for meta tags

### Established Patterns
- Municipality filter: same ilike + fail-open pattern as `get_ada_compliance_grants()` in api/routes.py
- Template responses: `templates.TemplateResponse(request, name, context={...})`
- Redirects: `from fastapi.responses import RedirectResponse` with `status_code=301`
- Route ordering: static routes before path params (ada-compliance route before /{opportunity_id})

### Integration Points
- Widget route registered in `grantflow/web/routes.py`
- /ada-grants redirect registered in `grantflow/web/routes.py`
- Template served from `templates/` directory (Jinja2)

</code_context>

<specifics>
## Specific Ideas

- DOT FTA "All Stations Access" grant closes 2026-05-01 — highlight this deadline prominently
- Widget should be embeddable by ada-audit (ComplianceGrade integration) via iframe or fetch
- /ada-grants is the alternative URL (alias or redirect)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
