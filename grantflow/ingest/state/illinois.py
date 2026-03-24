"""Illinois state grant scraper — CKAN API (data.illinois.gov)."""

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

CKAN_BASE = "https://data.illinois.gov"
PAGE_SIZE = 1000


class IllinoisScraper(BaseStateScraper):
    """Fetch Illinois grant records from the CKAN API at data.illinois.gov."""

    source_name = "state_illinois"
    state_code = "il"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        dataset_id = os.getenv("GRANTFLOW_IL_DATASET_ID", "")

        if not dataset_id:
            log.warning(
                "ckan_dataset_id_missing",
                env_var="GRANTFLOW_IL_DATASET_ID",
                message="Set GRANTFLOW_IL_DATASET_ID to enable Illinois scraping",
            )
            return []

        client = httpx.Client(timeout=60)
        try:
            # Discover the datastore resource ID
            pkg_url = f"{CKAN_BASE}/api/3/action/package_show?id={dataset_id}"
            log.info("ckan_package_lookup", url=pkg_url)
            resp = client.get(pkg_url)
            resp.raise_for_status()
            pkg_data = resp.json()

            resources = pkg_data.get("result", {}).get("resources", [])
            resource_id = None
            for res in resources:
                fmt = (res.get("format") or "").upper()
                if fmt in ("CSV", "JSON") or res.get("datastore_active"):
                    resource_id = res.get("id")
                    log.info("ckan_resource_found", resource_id=resource_id, format=fmt)
                    break

            if not resource_id:
                log.warning("ckan_no_datastore_resource", dataset=dataset_id)
                return []

            # Paginate the datastore
            records: list[dict] = []
            offset = 0

            while True:
                search_url = (
                    f"{CKAN_BASE}/api/3/action/datastore_search"
                    f"?resource_id={resource_id}&limit={PAGE_SIZE}&offset={offset}"
                )
                log.debug("ckan_page_fetch", offset=offset)
                resp = client.get(search_url)
                resp.raise_for_status()
                data = resp.json()

                result = data.get("result", {})
                batch = result.get("records", [])
                total = result.get("total", 0)

                records.extend(batch)
                log.debug("ckan_page_received", count=len(batch), total=total)

                if not batch or offset + len(batch) >= total:
                    break

                offset += PAGE_SIZE
                time.sleep(STATE_SCRAPER_REQUEST_DELAY)

            log.info("ckan_fetch_complete", total_records=len(records))
            return records

        except httpx.HTTPStatusError as exc:
            log.error("ckan_http_error", status=exc.response.status_code, error=str(exc))
            raise
        except httpx.RequestError as exc:
            log.error("ckan_request_error", error=str(exc))
            raise
        finally:
            client.close()

    def normalize_record(self, raw: dict) -> dict | None:
        title = (raw.get("Title") or raw.get("grant_title") or raw.get("title") or "").strip()
        if not title:
            return None

        raw_agency = raw.get("Agency") or raw.get("agency_name") or raw.get("agency")
        agency_name = normalize_agency_name(raw_agency)
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[:50]

        source_id = str(raw.get("_id") or raw.get("id") or "")

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": raw.get("Description") or raw.get("description"),
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            "close_date": normalize_date(
                raw.get("Application_Due_Date") or raw.get("deadline") or raw.get("close_date")
            ),
            "post_date": normalize_date(
                raw.get("Posted_Date") or raw.get("open_date") or raw.get("post_date")
            ),
            "source_url": raw.get("URL") or raw.get("url") or "",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(raw, default=str),
        }
