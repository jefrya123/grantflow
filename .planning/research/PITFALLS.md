# Domain Pitfalls: Government Grants DaaS

**Domain:** Government grants/contracts data aggregation platform (DaaS)
**Researched:** 2026-03-24
**Confidence:** HIGH for scraper/pipeline pitfalls (well-documented); MEDIUM for GTM/pricing (less post-mortem literature)

---

## Critical Pitfalls

Mistakes that cause rewrites, churn, or the product becoming unsellable.

---

### Pitfall 1: Grants.gov Is Mid-Migration — Your Pipeline Will Break

**What goes wrong:** Grants.gov is actively migrating from its legacy SOAP/XML-bulk system to `simpler.grants.gov` REST APIs. The old XML bulk extract (your current source) and the legacy SOAP system are being deprecated. The new REST API (`search2`, `fetchOpportunity`) launched in March 2025 and is labeled "early development, subject to change." The detail endpoint is already down. If you don't track this migration, your ingest pipeline silently switches from "working" to "serving stale 2025 data forever" without you noticing.

**Why it happens:** Government API migrations move in geological time but don't announce breakage loudly. The S2S (system-to-system) users get notified via the WordPress blog that almost nobody monitors.

**Consequences:** The primary data source goes dark mid-pipeline, 81K records stop refreshing, and users silently get stale data. Trust breaks before you've charged anyone.

**Warning signs:**
- `_find_extract_url` in `grants_gov.py` exhausting all 21 URL patterns without success
- HTTP 404/410 on the bulk XML S3 bucket
- No ingestion log entries for Grants.gov after a run

**Prevention:**
- Add an explicit health check: after every Grants.gov ingest, assert the record count is within ±20% of the previous run. Alert loudly if not.
- Subscribe to `grantsgovprod.wordpress.com` RSS feed for migration announcements.
- Plan for dual-source ingest: XML bulk extract today + REST API when stable. Do not rip out XML until REST is proven reliable for 30+ days.
- Phase mapping: **Pipeline hardening phase** — add alerting before anything else.

**Sources:** Grants.gov API Releases blog (March 2025 REST launch); Simpler.Grants.gov wiki noting "subject to change"

---

### Pitfall 2: SAM.gov's 10 req/day Public Limit Is a Hard Wall

**What goes wrong:** SAM.gov public API is rate-limited at 10 requests/day without registration, and 1,000/day with a registered API key. This sounds fine until you realize: (a) you need a registered API key per system account, (b) limit increase requests are granted case-by-case and can be revoked, and (c) exceeding limits triggers automatic key suspension. For a full SAM.gov contract dataset this limit is comically low — federal procurement has tens of thousands of new postings weekly.

**Why it happens:** SAM.gov is an IAE (Integrated Award Environment) system. GSA throttles it heavily to protect infrastructure stability, not as a business decision.

**Consequences:** A naive scraping approach hits the daily cap in the first endpoint call of a bulk sync run. You either get partial data or your key gets suspended.

**Warning signs:**
- HTTP 429 responses from api.sam.gov
- "Your API key has been temporarily blocked" response body
- SAM.gov records stopping at a suspiciously round number

**Prevention:**
- Design SAM.gov ingest as an incremental, spread-over-24-hours pipeline, not a bulk nightly job. Fetch modified-since-last-run only.
- Cache all responses locally. The opportunities data changes infrequently — use ETags/Last-Modified headers.
- Apply for the highest rate limit tier you can justify in the business description. Document the system account registration carefully.
- Phase mapping: **SAM.gov integration phase** — architect incrementally from day one, not as an afterthought.

---

### Pitfall 3: Scraper Rot — State Portals Will Break Without Warning

**What goes wrong:** State grant portals are not APIs. They are human-facing websites built on WordPress, Drupal, or bespoke CMS platforms with zero notice of changes. When a state redesigns their grants page (new CSS classes, new URL structure, moved to a new subdomain, added Cloudflare protection), your scraper silently returns empty results or worse: stale, malformed data that looks valid.

**Why it happens:** HTML scrapers are coupled to DOM structure. A redesign that takes a webmaster 4 hours can break a scraper that took 40 hours to build. State agencies have no contractual obligation to you and won't announce changes.

**Consequences:** For 25 states (your moat), scraper rot means your competitive differentiation silently erodes. By the time you notice, weeks of missing state data have gone out to paying customers.

**Warning signs:**
- Record count for a specific state drops to zero for 2+ consecutive days
- State scraper returns data but fields are empty strings (CSS selector matched wrong element)
- HTTP 403 from Cloudflare or similar WAF on a previously open page

**Prevention:**
- Instrument every scraper with per-source record count assertions. If a state that normally yields 50 records returns 0, fire an alert immediately — don't wait for the next run.
- Add a "last seen" timestamp per source. Surface data age in the API (`data_freshness_by_source`). This forces you to notice rot and builds customer trust.
- Use Scrapling (already in your stack) for its adaptive selectors, but do not rely on it blindly — treat it as reducing maintenance frequency, not eliminating it.
- Budget 2-4 hours/month per active state scraper for maintenance. For 10 states, that's ~20-40 hrs/month. If the product depends on this data, it must be staffed.
- Phase mapping: **State portal phase** — build monitoring/alerting before scraping the 10th portal. Don't let scraper count outpace your ability to monitor them.

---

### Pitfall 4: Cross-Source Duplicate Records Erode Search Quality

**What goes wrong:** The same grant opportunity appears in Grants.gov AND SBIR.gov AND potentially a state portal. If not deduplicated, search results show the same opportunity 2-3 times with slightly different field values (different close dates, different dollar amounts from different API snapshots), which looks broken to users and inflates your record counts.

**Why it happens:** CFDA/assistance listing numbers are the canonical link between sources, but they're stored inconsistently (leading zeros, spaces, hyphens). Your current `ilike` match on `cfda_numbers` is a full table scan that will miss format variations.

**Consequences:** A user searching for "SBIR Phase I energy" gets the same opportunity listed three times. They immediately question data quality and churn. Record count claims ("81K opportunities") become misleading if 15% are dupes.

**Warning signs:**
- Same `opportunity_title` + agency + close date appearing multiple times in search results
- `cfda_numbers` format varies across sources (e.g., `84.007` vs `84-007` vs `084.007`)
- `opportunity_id` from Grants.gov matches an SBIR record's `opportunity_number` field

**Prevention:**
- Define a canonical record identity: `(source_system, source_id)` is the internal key; a separate dedup layer creates a `canonical_opportunity_id` that groups cross-source records.
- Normalize CFDA numbers to a standard format (`84.007`) at ingest time, not at query time.
- Build a dedup report: run weekly, flag suspect duplicates for review. Don't automate deletion until confidence is high.
- Phase mapping: **Data quality phase** — must be solved before any public API launch, or first developer to integrate will report data quality issues immediately.

---

### Pitfall 5: Selling the API Before the Pipeline Is Proven Reliable

**What goes wrong:** You launch the paid API, a customer builds on it, and then the pipeline has a silent failure — Grants.gov changes a URL pattern, the cron job exits without error, the FTS index goes stale. The customer's product breaks on a Friday night. They churn and write a negative review.

**Why it happens:** There is currently no automated ingestion, no monitoring, no health check endpoint, and no alerting. The `ingestion_log` table exists but is not surfaced. This is the #1 known risk from the codebase audit.

**Consequences:** A DaaS product that delivers stale data is worse than no product. The freshness promise is the entire value proposition. Breaking it once early kills word-of-mouth.

**Warning signs:**
- No ingestion log entry in 25+ hours (daily pipeline missed)
- Last `updated_at` in the opportunities table is more than 36 hours ago
- API `/health` endpoint (currently absent) would catch this

**Prevention:**
- Automated daily pipeline must be running and monitored before you charge a single customer. No exceptions.
- Expose `/v1/status` endpoint with: `last_ingested_at` per source, `record_counts` per source, `pipeline_status` (ok/error/stale).
- Set up dead man's switch alerting: if the pipeline hasn't written to `ingestion_log` in 26 hours, send an alert.
- Phase mapping: **Pipeline hardening phase** — this is a prerequisite to GTM, not concurrent with it.

---

## Moderate Pitfalls

Mistakes that cause significant rework or customer friction but not existential risk.

---

### Pitfall 6: Breaking API Changes After Customers Integrate

**What goes wrong:** You ship v1 of the API, customers build on it, you then change field names or response shapes when adding state data (e.g., renaming `opportunity_status` to `status`, adding required fields). Every customer's integration breaks silently or loudly.

**Why it happens:** Without versioning, every API change is potentially breaking. The current API has no versioning. The serializer is hand-rolled and will diverge from the model silently (known from CONCERNS.md).

**Prevention:**
- Add `/v1/` URL prefix before any paying customers integrate. Route to a versioned response model.
- Use Pydantic response models (already recommended in CONCERNS.md) — they make breaking changes visible at the model layer before they reach customers.
- Adopt additive-only changes as the rule: add new fields, never rename or remove in the same version.
- Document the API response schema with OpenAPI spec from day one. Customers who see a schema will complain when you break it — that's good.
- Phase mapping: **Production API phase** — versioning must be in place before any external integrations.

---

### Pitfall 7: SQLite as the Production Database Breaks Under Concurrent Load

**What goes wrong:** SQLite WAL mode handles concurrent reads well but serializes all writes. When the daily ingestion pipeline runs (potentially 80K+ upserts), every API read queues behind the write lock. For 30-60 minutes during ingestion, the API is either slow or returns errors.

**Why it happens:** SQLite is single-writer. The ingestion pipeline and API server share the same process boundary, and FastAPI's async workers can't break WAL write locks.

**Warning signs:**
- API latency spikes during ingestion runs
- SQLite `database is locked` errors in logs during pipeline execution
- Ingestion duration growing as record counts grow

**Prevention:**
- Run ingestion into a separate staging database, then atomic swap. This gives zero-downtime ingestion regardless of database choice.
- Plan PostgreSQL migration before the first paid customer. SQLAlchemy models are already compatible — only `DATABASE_URL`, FTS (switch to `tsvector`/`pg_trgm`), and deployment config change.
- Phase mapping: **Pipeline hardening or production API phase** — whichever comes first.

---

### Pitfall 8: Pricing on Volume When Buyers Value Coverage

**What goes wrong:** You price the API on requests/month (call volume), but grant researchers and grant-adjacent SaaS products don't care how many API calls they make — they care whether you have the data they need. A researcher checks 5 grants deeply; a SaaS product syncs your entire dataset once/week. Per-call pricing penalizes the SaaS integrator and under-charges the deep researcher.

**Why it happens:** Per-call pricing is the default API pricing mental model. It optimizes for the wrong thing in a data coverage business.

**Consequences:** You lose the most valuable customer segment (B2B SaaS integrators who will pay $500/mo for full dataset access) because your per-call pricing makes a weekly full sync look expensive. You retain low-value casual users.

**Prevention:**
- Price on dataset access tiers, not call volume. Tiers by: source coverage (federal-only vs. federal+state), refresh frequency (weekly vs. daily), and support level.
- Example validated by Instrumentl's model: workflow/seat-based for end users; dataset license for API builders. Don't conflate both into one pricing model.
- Test with direct outreach before building a billing system. Ask 5 potential B2B buyers "what would you pay for X?" before implementing Stripe.
- Phase mapping: **GTM validation phase** — validate pricing model with conversations before locking in tiers.

---

### Pitfall 9: Treating Federal Data Coverage as Sufficient

**What goes wrong:** Federal grant data (Grants.gov, SAM.gov) is publicly available from multiple free sources. A developer who wants only federal data can hit the government APIs directly, work around the limits, and never need you. If you don't have the state data moat operational, you're competing with free.

**Why it happens:** Federal data is easier to ingest (APIs exist, even if broken). State data is hard (scraping, portal diversity, maintenance). Teams build what's easy and defer what's hard.

**Consequences:** You launch, developers look at your federal-only data, compare it to what they can get from Grants.gov directly, and see no reason to pay. Churn before you've even built the moat.

**Prevention:**
- Do not launch paid tier until at least 5-7 states are live and surfaced visibly in the product. The state coverage is the primary reason to pay.
- Lead with state data in GTM messaging, not federal data. "The only API with state grants data" is the pitch, not "we normalized Grants.gov."
- Track which states are live in the product's public status page. This signals progress to potential buyers and creates accountability.
- Phase mapping: **State portal phase must complete before GTM launch**, not in parallel.

---

### Pitfall 10: Data Enrichment Debt — LLM Categorization Baked Into Ingest

**What goes wrong:** You add LLM-based categorization (eligibility parsing, topic classification) directly into the ingestion pipeline. The LLM call adds cost and latency to every upsert. When the prompt changes or the model is updated, you need to re-process all 81K records. If the LLM provider has an outage, the ingestion pipeline fails entirely.

**Why it happens:** Enrichment feels like a natural addition to the ingest step. It's not — it's a separate processing layer with different latency, cost, and failure characteristics.

**Prevention:**
- Keep raw ingest and enrichment as separate pipeline stages. Stage 1: ingest raw data, write to `opportunities`. Stage 2: enrichment worker reads unprocessed records, writes to `opportunity_enrichments` or separate columns.
- Store enrichment results separately with a `enriched_at` timestamp and `enrichment_model_version`. This enables re-processing without touching raw data.
- Enrichment pipeline failures must not block raw data availability.
- Phase mapping: **Data quality/enrichment phase** — design the pipeline architecture before writing the first LLM call.

---

## Minor Pitfalls

Friction-causing issues worth knowing about but not project-threatening.

---

### Pitfall 11: Search Result Relevance Degrades With Scale

**What goes wrong:** SQLite FTS5 returns results by BM25 relevance, which works well at 80K records. At 500K+ records (after state data), relevance tuning matters — a search for "small business energy grants" shouldn't rank a 1994 closed opportunity above a current one. Without date-boosting and status-boosting in the ranking, stale records crowd the top.

**Prevention:**
- Add a composite rank: `BM25_score * recency_weight * status_weight`. Closed/expired opportunities should be demoted, not excluded.
- Test search quality with 20 representative queries before and after adding state data.
- Phase mapping: **Search experience phase**.

---

### Pitfall 12: State Portal Legal Ambiguity

**What goes wrong:** State government data is NOT automatically in the public domain the way federal data is. 17 U.S.C. § 105 applies only to federal works. State laws vary: California, for example, has complex rules about government data ownership. Some state portals have ToS that restrict automated access.

**Why it matters for GrantFlow:** The project constraint says "zero legal risk tolerance." This constraint is met for federal data but requires per-state verification for state data.

**Prevention:**
- Before scraping each state portal, check: (a) the portal's ToS/robots.txt for scraping prohibitions, (b) whether the state has an open data policy, (c) whether the data is published under an open license.
- Document the legal basis for each state scraper in a `scrapers/STATE/LEGAL.md` file. This is the paper trail if ever challenged.
- Prioritize states with explicit open data portals (e.g., state.gov/data, data.state.gov subdomains) — they've already solved the licensing question.
- Phase mapping: **State portal phase** — legal check is the first step, before any scraping work starts.

---

### Pitfall 13: Exposing Raw Government Field Names in the API

**What goes wrong:** You expose the API using Grants.gov's raw field names (`OpportunityID`, `CFDANumbers`, `CloseDate`). When you add SAM.gov contracts and state data, those sources use different field names for the same concept. You end up with a schizophrenic API where `close_date` exists for some records and `response_deadline` for others.

**Prevention:**
- Define a canonical GrantFlow schema before the public API launch. Map every source's fields to canonical names during ingest. The API always returns canonical names.
- Document field mappings in a `docs/field-mappings.md`. This is also valuable SEO content for developers searching "how to query Grants.gov fields."
- Phase mapping: **Production API phase** — canonical schema must precede any external documentation.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Pipeline hardening | Grants.gov migration breaking XML source silently | Add record-count alerting + RSS monitoring before hardening |
| Pipeline hardening | SQLite write contention during ingestion | Stage-to-swap pattern or PostgreSQL migration |
| SAM.gov integration | 10 req/day public limit, key suspension | Incremental ingest + caching from day one |
| State portals | Scraper rot on every portal redesign | Per-source count assertions + alerting before scaling to 5+ states |
| State portals | State-level legal ambiguity | ToS/robots.txt review per state before scraping begins |
| Data quality | Cross-source duplicates destroying search UX | Canonical dedup layer before public API launch |
| Data quality | LLM enrichment coupled to ingest pipeline | Separate enrichment as independent pipeline stage |
| Production API | Breaking changes after customers integrate | `/v1/` versioning + Pydantic response models from day one |
| Production API | No freshness signal in API responses | `/v1/status` endpoint with per-source freshness data |
| GTM validation | Pricing on call volume vs. coverage value | Validate pricing model with 5 buyer conversations before Stripe |
| GTM launch | Launching with only federal data | State coverage (5+ states) must be live before paid tier launch |

---

## Sources

- Grants.gov API Resources: https://www.grants.gov/api
- Simpler.Grants.gov API Wiki (subject to change notice): https://wiki.simpler.grants.gov/product/api
- SAM.gov Rate Limits (1000/day): https://govconapi.com/sam-gov-rate-limits-reality
- 17 U.S.C. § 105 (federal works, public domain): https://www.law.cornell.edu/uscode/text/17/105
- hiQ v. LinkedIn, Meta v. Bright Data precedents (public scraping legality): https://scrapecreators.com/blog/is-web-scraping-legal-a-guide-based-on-recent-court-ruling
- SafeGraph DaaS Bible (pricing, GTM patterns): https://www.safegraph.com/blog/data-as-a-service-bible-everything-you-wanted-to-know-about-running-daas-companies
- ScrapingBee scraping challenges 2025: https://www.scrapingbee.com/blog/web-scraping-challenges/
- Instrumentl pricing (dataset vs. workflow tiers): https://www.instrumentl.com/pricing
- API versioning pitfalls: https://irina.codes/api-versioning-a-deep-dive/
- GrantFlow CONCERNS.md (internal codebase audit, 2026-03-24)
