"""North Carolina state grant scraper — OSBM Legislative Grants Database (CSV)."""

from __future__ import annotations

import csv
import io
import json
import re

import httpx

from grantflow.config import STATE_SCRAPER_REQUEST_DELAY  # noqa: F401 (used implicitly)
from grantflow.ingest.state.base import BaseStateScraper
from grantflow.normalizers import normalize_agency_name, normalize_date
from grantflow.pipeline.logging import bind_source_logger

# OSBM Legislative Grants Database CSV export — updated each legislative session.
# Source: https://www.osbm.nc.gov/grants/legislative-grants-database
# This CSV contains county-level directed grant allocations passed by the NC General Assembly.
# The VersionId pins this to the 2023-25 biennium dataset with short-session updates (Aug 2024).
CSV_URL = (
    "https://files.nc.gov/osbm/2024-08/"
    "23-25%20Directed%20Grants_w_Short%20Session%20Updates.csv"
    "?VersionId=u03aiNrIBC_GnX_h.jUjJXurNejZ1AOE"
)

# NC State agency abbreviation map for common abbreviations in OSBM data
_NC_AGENCY_MAP = {
    "DOT": "NC Department of Transportation",
    "DEQ": "NC Department of Environmental Quality",
    "DPS": "NC Department of Public Safety",
    "DHHS": "NC Department of Health and Human Services",
    "DNCR": "NC Department of Natural and Cultural Resources",
    "DPI": "NC Department of Public Instruction",
    "OSBM": "NC Office of State Budget and Management",
    "NCDA": "NC Department of Agriculture and Consumer Services",
    "NCDEQ": "NC Department of Environmental Quality",
    "NCDOT": "NC Department of Transportation",
    "NCDPS": "NC Department of Public Safety",
    "NCDHHS": "NC Department of Health and Human Services",
    "DCR": "NC Department of Natural and Cultural Resources",
    "DA&CS": "NC Department of Agriculture and Consumer Services",
    "COMMERCE": "NC Department of Commerce",
}


def _expand_nc_agency(abbrev: str) -> str:
    """Expand NC agency abbreviations to full names."""
    if not abbrev:
        return abbrev
    upper = abbrev.strip().upper()
    return _NC_AGENCY_MAP.get(upper, abbrev.strip())


class NorthCarolinaScraper(BaseStateScraper):
    """Fetch North Carolina county-level grant records from the OSBM Legislative Grants Database.

    Data source: NC Office of State Budget and Management (osbm.nc.gov)
    Coverage: Directed grants allocated by the NC General Assembly, 2023-25 biennium.
    County-level: Each record maps a specific grant award to a NC county and recipient.
    """

    source_name = "state_north_carolina"
    state_code = "nc"

    def fetch_records(self) -> list[dict]:
        log = bind_source_logger(self.source_name)
        client = httpx.Client(timeout=60)

        try:
            log.info("nc_osbm_fetch", url=CSV_URL)
            resp = client.get(CSV_URL, follow_redirects=True)
            resp.raise_for_status()

            # Parse CSV
            reader = csv.DictReader(io.StringIO(resp.text))
            records = list(reader)

            log.info("nc_osbm_fetch_complete", total_records=len(records))
            return records

        except httpx.HTTPStatusError as exc:
            log.error("nc_osbm_http_error", status=exc.response.status_code, error=str(exc))
            raise
        except httpx.RequestError as exc:
            log.error("nc_osbm_request_error", error=str(exc))
            raise
        finally:
            client.close()

    def normalize_record(self, raw: dict) -> dict | None:
        # Required field: organization receiving the grant
        org = (raw.get("Organization Receiving Funding") or "").strip()
        if not org:
            return None

        county = (raw.get("County") or "").strip()
        agency_abbrev = (raw.get("Administering Agency") or "").strip()
        agency_name = normalize_agency_name(_expand_nc_agency(agency_abbrev)) or agency_abbrev
        agency_slug = ""
        if agency_name:
            agency_slug = re.sub(r"[^a-z0-9]+", "_", agency_name.lower()).strip("_")[:50]

        # Title: include county to make records searchable by county
        if county:
            title = f"{county} County — {org}"
        else:
            title = org

        # Source of funds and session law provide description context
        source_of_funds = (raw.get("Source of Funds") or "").strip()
        session_law = (raw.get("Session Law") or "").strip()
        item_num = (raw.get("Item #") or "").strip()
        description_parts = []
        if source_of_funds:
            description_parts.append(f"Source of Funds: {source_of_funds}")
        if session_law:
            description_parts.append(f"Session Law: {session_law}")
        if item_num:
            description_parts.append(f"Item: {item_num}")
        if county:
            description_parts.append(f"County: {county}")
        description = ". ".join(description_parts) if description_parts else None

        # Build a stable source_id from county + org + item_num
        raw_id = f"{county}_{org}_{item_num}".lower()
        source_id = re.sub(r"[^a-z0-9]+", "_", raw_id).strip("_")[:80]

        # Award amounts — FY2023-24 and FY2024-25 columns
        # Store in additional_info since Opportunity schema doesn't have a dedicated field
        fy_2324 = (raw.get("FY2023-24") or "").strip()
        fy_2425 = (raw.get("FY2024-25") or "").strip()

        return {
            "id": self.make_opportunity_id(source_id),
            "source": self.source_name,
            "title": title,
            "description": description,
            "agency_name": agency_name,
            "agency_code": agency_slug or None,
            # NC legislative grants have no specific open/close dates — they are
            # appropriations tied to the legislative session
            "close_date": normalize_date(None),
            "post_date": normalize_date(None),
            "source_url": "https://www.osbm.nc.gov/grants/legislative-grants-database",
            "category": "State Grant",
            "opportunity_status": "posted",
            "raw_data": json.dumps(
                {
                    **raw,
                    "_county": county,
                    "_fy_2324": fy_2324,
                    "_fy_2425": fy_2425,
                },
                default=str,
            ),
        }
