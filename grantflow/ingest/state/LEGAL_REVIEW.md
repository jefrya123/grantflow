# State Portal Legal Review

**Reviewed:** 2026-03-24
**Reviewer:** Engineering (automated documentation)
**Precedent:** HiQ v. LinkedIn (9th Cir. 2022) — publicly accessible government data is not protected by CFAA
**Default rate limit:** 1 req/2s when portal policy is undocumented

---

## Review Checklist Template

For each portal the following items are evaluated:

| Check | Pass / Fail / Conditional |
|-------|--------------------------|
| robots.txt allows API/data access | |
| ToS contains no "no automated access", "no scraping", "no commercial use" prohibition | |
| Data is under an open license (CC0, CC-BY, or explicit Open Data policy) | |
| No authentication required to access data | |
| Rate limit policy documented (or default 1 req/2s applied) | |

---

## 1. California — data.ca.gov

**Portal:** https://data.ca.gov (CKAN-based)
**Scraper target:** California Grants Portal dataset via CKAN API
**Statutory basis:** California Grant Information Act of 2018 (Cal. Gov. Code § 8898 et seq.) — mandates public disclosure of state grant opportunities

| Check | Result |
|-------|--------|
| robots.txt | Allows API access; no Disallow on /api/ paths |
| ToS | State government public domain data; no restriction on automated access |
| Open Data License | CC0 (public domain dedication) — explicit on data.ca.gov |
| Authentication required | No — public CKAN API, no key required |
| Rate limit policy | Not documented; apply default 1 req/2s |

**Status: APPROVED**

---

## 2. New York — data.ny.gov

**Portal:** https://data.ny.gov (Socrata-based)
**Scraper target:** NY grants/funding datasets via Socrata SODA API
**Statutory basis:** NY Open Data Law (Executive Order 95, 2013; NY Pub Off Law § 87-e)

| Check | Result |
|-------|--------|
| robots.txt | Allows API access; no Disallow on /resource/ API paths |
| ToS | data.ny.gov Terms of Use explicitly permit open, unrestricted use for non-commercial and commercial purposes |
| Open Data License | NY Open Data License — permits free reuse with attribution |
| Authentication required | No — public Socrata API; app token optional for higher throughput |
| Rate limit policy | Socrata: 1000 req/hour unauthenticated; 100 req/second with app token |

**Status: APPROVED**

---

## 3. Illinois — data.illinois.gov

**Portal:** https://data.illinois.gov (CKAN-based)
**Scraper target:** Illinois grants datasets via CKAN API
**Statutory basis:** Open Operating Standards Act, PA 98-627 (2014) — state mandate for open data publication

| Check | Result |
|-------|--------|
| robots.txt | Allows API access; CKAN /api/ paths not disallowed |
| ToS | State government open data policy; no restriction on automated access |
| Open Data License | Identified as Open Data under state mandate; CC0 or equivalent implied |
| Authentication required | No — public CKAN API |
| Rate limit policy | Not documented; apply default 1 req/2s |

**Status: APPROVED**

---

## 4. Texas — data.texas.gov

**Portal:** https://data.texas.gov (Socrata-based)
**Scraper target:** Texas grants/funding datasets via Socrata SODA API
**Statutory basis:** SB 819 (2019) — Texas Open Data Portal mandate; HB 1988 (2021) reinforces open data requirements

| Check | Result |
|-------|--------|
| robots.txt | Allows API access; Socrata /resource/ paths not disallowed |
| ToS | Texas Open Data Portal: explicitly permits unrestricted use and redistribution |
| Open Data License | Public domain / Open Data Commons |
| Authentication required | No — public Socrata API; app token optional |
| Rate limit policy | Socrata defaults: 1000 req/hour unauthenticated |

**Status: APPROVED** *(pending dataset ID confirmation — verify the specific grants dataset ID before production scraping)*

---

## 5. North Carolina — osbm.nc.gov / files.nc.gov

**Portal:** https://www.osbm.nc.gov/grants/legislative-grants-database
**Scraper target:** OSBM Legislative Grants Database CSV (county-level directed grants)
**Statutory basis:** NC General Statutes Chapter 143C (State Budget Act) — requires public disclosure of appropriations; OSBM publishes grant data as part of budget transparency obligations

| Check | Result |
|-------|--------|
| robots.txt | www.osbm.nc.gov is a state government domain; files.nc.gov is the state's file hosting CDN — no robots.txt restrictions on public document URLs |
| ToS | State government public domain data; NC open data policy permits unrestricted reuse of government data |
| Open Data License | State government appropriations data — public domain by nature; no explicit CC0 but government data is not subject to copyright under state equivalent of 17 U.S.C. § 105 |
| Authentication required | No — direct public CSV download, no key or login required |
| Rate limit policy | Static CSV file download, not an API; one download per run, no rate limit concerns |

**Status: APPROVED**

**Note:** The CSV URL includes a VersionId parameter pinning it to the 2023-25 biennium dataset. This URL should be updated when OSBM publishes the 2025-27 biennium dataset.

---

## 6. Colorado — colorado.gov / choosecolorado.com

**Portal:** https://www.colorado.gov or https://choosecolorado.com
**Scraper target:** Colorado grants listings (no unified open data portal identified)
**Statutory basis:** No centralized open data mandate identified as of 2026-03

| Check | Result |
|-------|--------|
| robots.txt | NOT VERIFIED — must check before scraping |
| ToS | NOT VERIFIED — colorado.gov ToS must be reviewed for automated access restrictions |
| Open Data License | NOT VERIFIED — no explicit open data license identified |
| Authentication required | Unknown — must verify |
| Rate limit policy | Unknown — must verify; default 1 req/2s applies if undocumented |

**Status: CONDITIONAL — DO NOT SCRAPE until the following are confirmed:**
1. robots.txt allows automated access to grant listing pages
2. colorado.gov / choosecolorado.com ToS does not prohibit scraping or automated access
3. An explicit open data license or equivalent government public domain assertion is identified
4. No authentication gate is present

If no open data portal is available, consider contacting the Colorado Office of Economic Development for an API or data export agreement.

---

## Summary

| State | Portal | API Type | License | Status |
|-------|--------|----------|---------|--------|
| California | data.ca.gov | CKAN | CC0 | APPROVED |
| North Carolina | osbm.nc.gov / files.nc.gov | CSV download | State public domain | APPROVED |
| New York | data.ny.gov | Socrata | NY Open Data | APPROVED |
| Illinois | data.illinois.gov | Socrata | State Open Data | APPROVED |
| Texas | data.texas.gov | Socrata | Public Domain | APPROVED (dataset ID confirmed: pp37-5cwt) |
| Colorado | colorado.gov | Unknown | Unknown | CONDITIONAL |

---

## Legal Notes

- **HiQ v. LinkedIn (9th Cir. 2022):** Accessing publicly available data does not violate CFAA. Applies here as all approved portals are publicly accessible without authentication.
- **Government data:** All approved portals are operated by state governments under open data mandates. Government-produced data in the US is generally not subject to copyright (17 U.S.C. § 105 for federal; state equivalents vary but open data mandates typically waive restrictions).
- **Rate limiting:** Respect documented rate limits. Apply 1 req/2s default where undocumented. `STATE_SCRAPER_REQUEST_DELAY` config var controls this.
- **Re-review cadence:** Re-review ToS and robots.txt annually or when portal infrastructure changes.
