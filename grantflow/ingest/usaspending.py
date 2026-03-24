"""Pull recent grant awards from the USAspending.gov API."""

import json
import logging
from datetime import datetime, timezone, timedelta

import httpx

from grantflow.config import USASPENDING_API_BASE
from grantflow.database import SessionLocal
from grantflow.models import Award, Agency, IngestionLog

logger = logging.getLogger(__name__)

SEARCH_ENDPOINT = f"{USASPENDING_API_BASE}/search/spending_by_award/"

# Grant/cooperative agreement type codes
GRANT_TYPE_CODES = ["02", "03", "04", "05"]

# Fields to request from the API
REQUEST_FIELDS = [
    "Award ID",
    "Description",
    "Start Date",
    "End Date",
    "Award Amount",
    "Awarding Agency",
    "Awarding Sub Agency",
    "Recipient Name",
    "Place of Performance State Code",
    "Place of Performance City Name",
    "CFDA Number",
    "Award Type",
]

PER_PAGE = 100
MAX_RECORDS = 5000


def _build_request_body(page: int) -> dict:
    """Build the POST body for the USAspending search API."""
    today = datetime.now(timezone.utc)
    two_years_ago = today - timedelta(days=730)

    return {
        "filters": {
            "time_period": [
                {
                    "start_date": two_years_ago.strftime("%Y-%m-%d"),
                    "end_date": today.strftime("%Y-%m-%d"),
                }
            ],
            "award_type_codes": GRANT_TYPE_CODES,
        },
        "fields": REQUEST_FIELDS,
        "limit": PER_PAGE,
        "page": page,
        "order": "desc",
        "sort": "Award Amount",
    }


def _parse_award(row: dict) -> dict:
    """Parse a single award row from the API response."""
    award_id_raw = row.get("Award ID") or ""
    award_id_raw = award_id_raw.strip()
    if not award_id_raw:
        return {}

    amount = row.get("Award Amount")
    if amount is not None:
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            amount = None

    return {
        "id": f"usaspending_{award_id_raw}",
        "source": "usaspending",
        "award_id": award_id_raw,
        "title": row.get("Description", ""),
        "description": row.get("Description", ""),
        "agency_name": row.get("Awarding Agency", ""),
        "agency_code": row.get("Awarding Sub Agency", ""),
        "cfda_numbers": row.get("CFDA Number", ""),
        "recipient_name": row.get("Recipient Name", ""),
        "award_amount": amount,
        "start_date": row.get("Start Date"),
        "end_date": row.get("End Date"),
        "award_date": row.get("Start Date"),
        "place_state": row.get("Place of Performance State Code", ""),
        "place_city": row.get("Place of Performance City Name", ""),
        "award_type": row.get("Award Type", ""),
        "raw_data": json.dumps(row),
    }


def ingest_usaspending() -> dict:
    """Pull grant awards from USAspending.gov API. Returns stats dict."""
    stats = {
        "source": "usaspending",
        "status": "error",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "error": None,
    }
    started_at = datetime.now(timezone.utc).isoformat()

    session = SessionLocal()
    log_entry = IngestionLog(
        source="usaspending",
        started_at=started_at,
        status="running",
    )
    session.add(log_entry)
    session.commit()

    try:
        agencies_seen: dict[str, str] = {}
        page = 1
        total_fetched = 0

        with httpx.Client(timeout=60) as client:
            while total_fetched < MAX_RECORDS:
                body = _build_request_body(page)
                logger.info("Fetching USAspending page %d ...", page)

                resp = client.post(SEARCH_ENDPOINT, json=body)
                resp.raise_for_status()
                data = resp.json()

                results = data.get("results", [])
                if not results:
                    logger.info("No more results at page %d", page)
                    break

                for row in results:
                    record = _parse_award(row)
                    if not record:
                        continue

                    stats["records_processed"] += 1
                    total_fetched += 1

                    # Track agencies
                    agency_name = record.get("agency_name", "")
                    sub_agency = record.get("agency_code", "")
                    if agency_name and agency_name not in agencies_seen:
                        agencies_seen[agency_name] = sub_agency

                    # Upsert award
                    existing = session.get(Award, record["id"])
                    if existing:
                        for key, value in record.items():
                            if key != "created_at":
                                setattr(existing, key, value)
                        stats["records_updated"] += 1
                    else:
                        record["created_at"] = datetime.now(timezone.utc).isoformat()
                        session.add(Award(**record))
                        stats["records_added"] += 1

                    if total_fetched >= MAX_RECORDS:
                        break

                # Flush every page
                session.flush()
                page += 1

                # Check if there are more pages
                has_next = data.get("page_metadata", {}).get("hasNext", False)
                if not has_next:
                    break

        # Upsert agencies
        for agency_name, sub_agency in agencies_seen.items():
            code = agency_name.replace(" ", "_").upper()[:50]
            existing = session.get(Agency, code)
            if not existing:
                session.add(Agency(
                    code=code,
                    name=agency_name,
                    parent_name=sub_agency if sub_agency != agency_name else None,
                ))

        session.commit()
        stats["status"] = "success"
        logger.info(
            "USAspending ingestion complete: %d processed, %d added, %d updated",
            stats["records_processed"],
            stats["records_added"],
            stats["records_updated"],
        )

    except Exception as e:
        logger.exception("USAspending ingestion failed: %s", e)
        stats["status"] = "error"
        stats["error"] = str(e)
        session.rollback()

    finally:
        log_entry.completed_at = datetime.now(timezone.utc).isoformat()
        log_entry.records_processed = stats["records_processed"]
        log_entry.records_added = stats["records_added"]
        log_entry.records_updated = stats["records_updated"]
        log_entry.status = stats["status"]
        log_entry.error = stats.get("error")
        try:
            session.commit()
        except Exception:
            session.rollback()
        session.close()

    return stats
