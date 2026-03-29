"""Colorado state grant scraper — httpx HTML (choosecolorado.com/doing-business/incentives/)."""

from __future__ import annotations

import json
import os
import re

import httpx

from grantflow.ingest.state.base import BaseStateScraper
from grantflow.normalizers import normalize_agency_name, normalize_date
from grantflow.pipeline.logging import bind_source_logger

DEFAULT_PORTAL_URL = "https://choosecolorado.com/doing-business/incentives/"
_BASE_URL = "https://choosecolorado.com"


class ColoradoScraper(BaseStateScraper):
    """Fetch Colorado grant/incentive listings from choosecolorado.com/doing-business/incentives/.

    Note: Colorado has no centralized open data portal. This scraper targets
    the Choose Colorado incentives page. Verify ToS/robots.txt before production use
    (per legal review: CONDITIONAL status).

    Uses httpx for static HTML fetching.
    """

    source_name = "state_colorado"
    state_code = "co"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        portal_url = os.getenv("GRANTFLOW_CO_PORTAL_URL", DEFAULT_PORTAL_URL)

        if not portal_url:
            log.warning(
                "colorado_portal_url_missing",
                env_var="GRANTFLOW_CO_PORTAL_URL",
                message="Set GRANTFLOW_CO_PORTAL_URL to enable Colorado scraping",
            )
            return []

        log.info("colorado_fetch_start", url=portal_url)

        try:
            resp = httpx.get(
                portal_url,
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; GrantFlow/1.0)"},
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            log.error(
                "colorado_fetch_http_error",
                status=exc.response.status_code,
                url=portal_url,
                error=str(exc),
            )
            raise
        except httpx.RequestError as exc:
            log.error("colorado_fetch_failed", url=portal_url, error=str(exc))
            raise

        html = resp.text
        log.debug("colorado_html_fetched", html_length=len(html))

        records = self._parse_incentives_page(html)

        if not records:
            log.warning(
                "colorado_no_records_found",
                html_length=len(html),
                message="No grant records extracted — portal structure may have changed",
            )

        log.info(
            "colorado_fetch_complete",
            total_records=len(records),
            html_length=len(html),
        )
        return records

    def _parse_incentives_page(self, html: str) -> list[dict]:
        """Parse the incentives page structure.

        The page uses: <p><strong><a href="...">Title</a>: </strong>Description</p>
        """
        # Pattern: paragraph with a bold link followed by a colon and description
        pattern = re.compile(
            r"<p[^>]*>"
            r"<strong[^>]*>"
            r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'
            r"[^<]*</strong>"
            r"([^<]*(?:<[^/][^>]*>[^<]*</[^>]+>[^<]*)*)"
            r"</p>",
            re.IGNORECASE | re.DOTALL,
        )

        records = []
        for match in pattern.finditer(html):
            href, title, desc_html = match.group(1), match.group(2), match.group(3)

            title = title.strip()
            if not title:
                continue

            # Strip any remaining HTML tags from description
            description = re.sub(r"<[^>]+>", " ", desc_html).strip()
            description = re.sub(r"\s+", " ", description).lstrip(": ").strip()

            # Resolve relative URLs
            if href.startswith("/"):
                href = _BASE_URL + href

            records.append(
                {
                    "title": title,
                    "description": description,
                    "agency": "Colorado Office of Economic Development and International Trade",
                    "deadline": "",
                    "url": href,
                }
            )

        return records

    _DEGRADED_THRESHOLD = 3

    def run(self, session=None) -> dict:  # type: ignore[override]
        """Run ingestion with low-record detection.

        If fetch_records() returns fewer than _DEGRADED_THRESHOLD records,
        return status='degraded' immediately instead of treating sparse data
        as a successful run.
        """
        log = bind_source_logger(self.source_name)

        try:
            raw_records = self.fetch_records()
        except Exception as exc:
            log.error("fetch_records_failed", error=str(exc))
            return {
                "source": self.source_name,
                "status": "error",
                "records_processed": 0,
                "records_added": 0,
                "records_updated": 0,
                "records_failed": 0,
                "error": str(exc),
            }

        count = len(raw_records)
        if count < self._DEGRADED_THRESHOLD:
            log.warning(
                "colorado_too_few_records",
                count=count,
                threshold=self._DEGRADED_THRESHOLD,
                message="Portal structure may have changed — marking run as degraded",
            )
            return {
                "source": self.source_name,
                "status": "degraded",
                "records_processed": count,
                "records_added": 0,
                "records_updated": 0,
                "records_failed": 0,
                "error": f"Too few records ({count}) — portal structure may have changed",
            }

        # Delegate to base class for normal processing
        return super().run(session=session)

    def normalize_record(self, raw: dict) -> dict | None:
        title = (raw.get("title") or "").strip()
        if not title:
            return None

        raw_agency = raw.get("agency") or raw.get("organization") or raw.get("grantor")
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[
                :50
            ]

        # Use title as source_id since Colorado portal lacks stable numeric IDs
        source_id = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:80]

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": raw.get("description") or raw.get("_raw_text"),
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            "close_date": normalize_date(raw.get("deadline") or raw.get("close_date")),
            "post_date": normalize_date(raw.get("posted_date") or raw.get("open_date")),
            "source_url": raw.get("url") or raw.get("link") or "",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(
                {k: v for k, v in raw.items() if k != "_raw_cells"},
                default=str,
            ),
        }
