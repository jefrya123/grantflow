"""Florida state grant scraper — Socrata API (data.myflorida.com)."""

from __future__ import annotations

import json
import os
import re
import time

import httpx

from grantflow.config import STATE_SCRAPER_REQUEST_DELAY
from grantflow.ingest.state.base import BaseStateScraper
from grantflow.normalizers import normalize_agency_name, normalize_date
from grantflow.pipeline.logging import bind_source_logger

# data.myflorida.com is Florida's financial accountability Socrata portal.
# Default dataset: wkrj-sdrb — "Grants and Aids Disbursements"
# Florida Department of Financial Services; award records with agency, grantee,
# fiscal year, amount, and project description.
SOCRATA_BASE = "https://data.myflorida.com"
DEFAULT_DATASET_ID = "wkrj-sdrb"
PAGE_SIZE = 1000


class FloridaScraper(BaseStateScraper):
    """Fetch Florida grant records from the Socrata API at data.myflorida.com."""

    source_name = "state_florida"
    state_code = "fl"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        # Allow override via env var; fall back to well-known grants dataset
        dataset_id = os.getenv("GRANTFLOW_FL_DATASET_ID", DEFAULT_DATASET_ID)

        client = httpx.Client(timeout=60)
        try:
            records: list[dict] = []
            offset = 0

            while True:
                url = (
                    f"{SOCRATA_BASE}/resource/{dataset_id}.json"
                    f"?$limit={PAGE_SIZE}&$offset={offset}"
                )
                log.debug("socrata_page_fetch", offset=offset, url=url)
                resp = client.get(url)
                resp.raise_for_status()
                batch: list[dict] = resp.json()

                records.extend(batch)
                log.debug("socrata_page_received", count=len(batch))

                if len(batch) < PAGE_SIZE:
                    break

                offset += PAGE_SIZE
                time.sleep(STATE_SCRAPER_REQUEST_DELAY)

            log.info("socrata_fetch_complete", total_records=len(records))
            return records

        except httpx.HTTPStatusError as exc:
            log.error(
                "socrata_http_error", status=exc.response.status_code, error=str(exc)
            )
            raise
        except httpx.RequestError as exc:
            log.error("socrata_request_error", error=str(exc))
            raise
        finally:
            client.close()

    def normalize_record(self, raw: dict) -> dict | None:
        # Handles Grants and Aids Disbursements dataset columns:
        #   agency_name, grantee_name, project_description, award_amount,
        #   fiscal_year, county_name, grant_number, begin_date, end_date
        # Also handles generic Socrata grant datasets with common field names.
        title = (
            raw.get("project_description")
            or raw.get("project_name")
            or raw.get("program_name")
            or raw.get("grant_title")
            or raw.get("title")
            or raw.get("Title")
            or ""
        ).strip()
        if not title:
            return None

        # Truncate long descriptions used as titles
        if len(title) > 200:
            title = title[:197] + "..."

        raw_agency = (
            raw.get("agency_name")
            or raw.get("grantor_agency")
            or raw.get("grantor")
            or raw.get("agency")
            or raw.get("Agency")
            or raw.get("funding_agency")
        )
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[
                :50
            ]

        # Build stable source_id from grant_number or composite key
        source_id = str(
            raw.get("grant_number")
            or raw.get(":id")
            or raw.get("_id")
            or raw.get("id")
            or ""
        )
        if not source_id:
            grantee = (raw.get("grantee_name") or raw.get("recipient") or "").lower()
            fy = raw.get("fiscal_year") or raw.get("fy") or ""
            county = (raw.get("county_name") or raw.get("county") or "").lower()
            raw_key = f"{fy}_{county}_{grantee}"
            source_id = re.sub(r"[^a-z0-9]+", "_", raw_key).strip("_")[:80]

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": (
                raw.get("description") or raw.get("Description") or raw.get("summary")
            ),
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            "close_date": normalize_date(
                raw.get("end_date")
                or raw.get("grant_end_date")
                or raw.get("completion_date")
                or raw.get("deadline")
            ),
            "post_date": normalize_date(
                raw.get("begin_date")
                or raw.get("grant_begin_date")
                or raw.get("award_date")
                or raw.get("start_date")
            ),
            "source_url": raw.get("url") or raw.get("URL") or "",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(raw, default=str),
        }
