"""Texas state grant scraper — Socrata API (data.texas.gov)."""

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

SOCRATA_BASE = "https://data.texas.gov"
# Default dataset: pp37-5cwt — "TCA All Approved Grants FY25"
# Texas Commission on the Arts; 1730 records with applicant, city, region, amount, project_title.
DEFAULT_DATASET_ID = "pp37-5cwt"
PAGE_SIZE = 1000


class TexasScraper(BaseStateScraper):
    """Fetch Texas grant records from the Socrata API at data.texas.gov."""

    source_name = "state_texas"
    state_code = "tx"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        # Allow override via env var; fall back to well-known TCA grants dataset
        dataset_id = os.getenv("GRANTFLOW_TX_DATASET_ID", DEFAULT_DATASET_ID)

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
        # Handles TCA dataset (pp37-5cwt) columns:
        #   application_id, applicant_name, city, region, amount, project_title, summary
        # Also handles generic grant datasets with common field names.
        applicant = (raw.get("applicant_name") or "").strip()
        project_title = (raw.get("project_title") or "").strip()

        # Build a descriptive title
        if applicant and project_title:
            title = f"{applicant} — {project_title}"
        elif applicant:
            title = applicant
        else:
            title = (
                raw.get("grant_name")
                or raw.get("program_name")
                or raw.get("title")
                or raw.get("name")
                or ""
            ).strip()

        if not title:
            return None

        # TCA grants are administered by Texas Commission on the Arts
        raw_agency = (
            raw.get("agency")
            or raw.get("agency_name")
            or raw.get("grantor")
            or raw.get("funding_agency")
            or "Texas Commission on the Arts"
        )
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[
                :50
            ]

        source_id = str(
            raw.get("application_id")
            or raw.get("_id")
            or raw.get("id")
            or raw.get("grant_id")
            or raw.get("program_id")
            or ""
        )

        description = (
            raw.get("summary")
            or raw.get("description")
            or raw.get("program_description")
        )
        if not description and raw.get("city") and raw.get("region"):
            description = f"City: {raw['city']}. Region: {raw['region']}."

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": description,
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            "close_date": normalize_date(
                raw.get("deadline")
                or raw.get("application_deadline")
                or raw.get("close_date")
            ),
            "post_date": normalize_date(
                raw.get("open_date") or raw.get("posted_date") or raw.get("start_date")
            ),
            "source_url": raw.get("url")
            or raw.get("link")
            or raw.get("source_url")
            or "",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(raw, default=str),
        }
