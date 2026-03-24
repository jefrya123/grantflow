"""Illinois state grant scraper — Socrata API (data.illinois.gov)."""

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

# data.illinois.gov is Socrata-based (not CKAN as originally assumed).
# Default dataset: q46r-i78b — "Grants to Illinois Artists and Arts Organizations"
# 10,000+ records, has program_name, grantor, grantee, award_amount, dates.
SOCRATA_BASE = "https://data.illinois.gov"
DEFAULT_DATASET_ID = "q46r-i78b"
PAGE_SIZE = 1000


class IllinoisScraper(BaseStateScraper):
    """Fetch Illinois grant records from the Socrata API at data.illinois.gov."""

    source_name = "state_illinois"
    state_code = "il"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        # Allow override via env var; fall back to well-known grants dataset
        dataset_id = os.getenv("GRANTFLOW_IL_DATASET_ID", DEFAULT_DATASET_ID)

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
            log.error("socrata_http_error", status=exc.response.status_code, error=str(exc))
            raise
        except httpx.RequestError as exc:
            log.error("socrata_request_error", error=str(exc))
            raise
        finally:
            client.close()

    def normalize_record(self, raw: dict) -> dict | None:
        # Dataset q46r-i78b columns: fiscal_year, applicant_applicant_name, applicant_zip,
        # application_application_name, grant_program, awarded_amount,
        # payment_authorization_date, term_start_date, term_end_date
        title = (
            raw.get("application_application_name")
            or raw.get("program_name")
            or raw.get("grant_program")
            or raw.get("Title")
            or raw.get("title")
            or ""
        ).strip()
        if not title:
            return None

        raw_agency = (
            raw.get("grantor")
            or raw.get("grantor_agency")
            or raw.get("agency")
            or raw.get("Agency")
            or raw.get("funding_agency")
        )
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[:50]

        source_id = str(
            raw.get(":id")
            or raw.get("_id")
            or raw.get("id")
            or ""
        )
        # Fall back to a composite key if no explicit ID
        if not source_id:
            applicant = (raw.get("applicant_applicant_name") or "").lower()
            program = (raw.get("grant_program") or raw.get("program_name") or "").lower()
            fy = raw.get("fiscal_year") or raw.get("fy") or ""
            raw_key = f"{fy}_{applicant}_{program}"
            source_id = re.sub(r"[^a-z0-9]+", "_", raw_key).strip("_")[:80]

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": (
                raw.get("description_of_purpose_of")
                or raw.get("program_description")
                or raw.get("Description")
                or raw.get("description")
            ),
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            "close_date": normalize_date(
                raw.get("completion_date")
                or raw.get("term_end_date")
                or raw.get("deadline")
                or raw.get("close_date")
            ),
            "post_date": normalize_date(
                raw.get("start_date")
                or raw.get("term_start_date")
                or raw.get("payment_authorization_date")
                or raw.get("Posted_Date")
                or raw.get("post_date")
            ),
            "source_url": raw.get("URL") or raw.get("url") or "",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(raw, default=str),
        }
