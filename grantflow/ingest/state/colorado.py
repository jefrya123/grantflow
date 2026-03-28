"""Colorado state grant scraper — Scrapling HTML (choosecolorado.com)."""

from __future__ import annotations

import json
import os
import re

from scrapling.fetchers import Fetcher

from grantflow.ingest.state.base import BaseStateScraper
from grantflow.normalizers import normalize_agency_name, normalize_date
from grantflow.pipeline.logging import bind_source_logger

DEFAULT_PORTAL_URL = "https://choosecolorado.com/doing-business/support-services/grants/"


class ColoradoScraper(BaseStateScraper):
    """Fetch Colorado grant listings from the HTML portal using Scrapling.

    Note: Colorado has no centralized open data portal. This scraper targets
    the Choose Colorado grants page. Verify ToS/robots.txt before production use
    (per legal review: CONDITIONAL status).

    Uses Scrapling Fetcher (static HTML only — no StealthyFetcher/DynamicFetcher
    needed for government portals).
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
        fetcher = Fetcher(auto_match=True)

        try:
            page = fetcher.get(portal_url, timeout=30)
        except Exception as exc:
            log.error("colorado_fetch_failed", error=str(exc))
            raise

        raw_html_len = len(page.html_content) if hasattr(page, "html_content") else len(str(page))
        log.debug("colorado_html_fetched", html_length=raw_html_len)

        records: list[dict] = []

        # Try table rows first (structured grants table)
        table_rows = page.css("table tbody tr", auto_save=True)
        if table_rows:
            log.debug("colorado_table_rows_found", count=len(table_rows))
            for row in table_rows:
                cells = row.css("td")
                if not cells:
                    continue
                cell_texts = [c.text.strip() for c in cells]
                if not cell_texts:
                    continue

                # Attempt to extract a link from the first cell
                link_el = row.css("a")
                href = link_el[0].attrib.get("href", "") if link_el else ""

                record: dict = {
                    "title": cell_texts[0] if len(cell_texts) > 0 else "",
                    "agency": cell_texts[1] if len(cell_texts) > 1 else "",
                    "deadline": cell_texts[2] if len(cell_texts) > 2 else "",
                    "url": href,
                    "_raw_cells": cell_texts,
                }
                records.append(record)

        # Fall back to list items or article cards
        if not records:
            items = (
                page.css("ul.grants-list li", auto_save=True)
                or page.css(".grant-item", auto_save=True)
                or page.css("article", auto_save=True)
                or page.css(".entry-content li", auto_save=True)
            )
            log.debug("colorado_list_items_found", count=len(items) if items else 0)
            for item in (items or []):
                link_el = item.css("a")
                href = link_el[0].attrib.get("href", "") if link_el else ""
                title_text = (
                    (link_el[0].text.strip() if link_el else "")
                    or (item.css("h2, h3, h4, strong")[0].text.strip() if item.css("h2, h3, h4, strong") else "")
                    or item.text.strip()
                )
                record = {
                    "title": title_text,
                    "agency": "",
                    "deadline": "",
                    "url": href,
                    "_raw_text": item.text.strip()[:500],
                }
                records.append(record)

        if not records:
            log.warning(
                "colorado_no_records_found",
                html_length=raw_html_len,
                message="No grant records extracted — portal structure may have changed",
            )

        log.info("colorado_fetch_complete", total_records=len(records), html_length=raw_html_len)
        return records

    def normalize_record(self, raw: dict) -> dict | None:
        title = (raw.get("title") or "").strip()
        if not title:
            return None

        raw_agency = raw.get("agency") or raw.get("organization") or raw.get("grantor")
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[:50]

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
