"""Download and parse the Grants.gov XML bulk extract or REST API."""

import json
import logging  # noqa: F401 — kept for any stdlib callers
import re
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from grantflow.config import (
    DATA_DIR,
    GRANTS_GOV_XML_URL,
    GRANTS_GOV_REST_API_BASE,
    GRANTS_GOV_USE_REST,
)
from grantflow.database import SessionLocal
from grantflow.models import Opportunity, IngestionLog
from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
    normalize_category,
    normalize_funding_instrument,
    validate_award_amounts,
)

from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("grants_gov")

# ─── REST API constants ────────────────────────────────────────────────────────

SEARCH2_ENDPOINT = f"{GRANTS_GOV_REST_API_BASE}/search2"
REST_PAGE_SIZE = 25        # API maximum per page
MIN_REST_THRESHOLD = 100   # fewer records than this = treat REST as unreliable
MAX_REST_PAGES = 200       # 200 × 25 = 5,000 record cap; prevent infinite pagination

# Field mapping for REST oppHit → Opportunity columns
REST_FIELD_MAP = {
    "id": "source_id",
    "title": "title",
    "number": "opportunity_number",
    "agencyName": "agency_name",
    "agencyCode": "agency_code",
    "openDate": "post_date",
    "closeDate": "close_date",
    "opportunityCategory": "category",
    "awardCeiling": "award_ceiling",
    "awardFloor": "award_floor",
    "description": "description",
}

# ─── XML constants ─────────────────────────────────────────────────────────────

# Fields to extract from each OpportunitySynopsisDetail element
FIELD_MAP = {
    "OpportunityID": "source_id",
    "OpportunityTitle": "title",
    "OpportunityNumber": "opportunity_number",
    "OpportunityCategory": "category",
    "FundingInstrumentType": "funding_instrument",
    "CategoryOfFundingActivity": None,  # stored in raw_data
    "CFDANumbers": "cfda_numbers",
    "EligibleApplicants": "eligible_applicants",
    "AdditionalInformationOnEligibility": None,
    "AgencyCode": "agency_code",
    "AgencyName": "agency_name",
    "PostDate": "post_date",
    "CloseDate": "close_date",
    "LastUpdatedDate": "last_updated",
    "AwardCeiling": "award_ceiling",
    "AwardFloor": "award_floor",
    "EstimatedTotalProgramFunding": "estimated_total_funding",
    "ExpectedNumberOfAwards": "expected_number_of_awards",
    "Description": "description",
    "CostSharingOrMatchingRequirement": "cost_sharing_required",
    "AdditionalInformationURL": "additional_info_url",
    "GrantorContactEmail": "contact_email",
    "GrantorContactText": "contact_text",
    "ArchiveDate": None,
    "CloseDateExplanation": None,
}

DATE_FIELDS = {"PostDate", "CloseDate", "LastUpdatedDate", "ArchiveDate"}
FLOAT_FIELDS = {"AwardCeiling", "AwardFloor", "EstimatedTotalProgramFunding"}
INT_FIELDS = {"ExpectedNumberOfAwards"}
BOOL_FIELDS = {"CostSharingOrMatchingRequirement"}


# ─── Shared helpers ────────────────────────────────────────────────────────────


def _upsert_batch(session, batch: list[dict], stats: dict) -> None:
    """Upsert a batch of opportunity records."""
    for record in batch:
        opp_id = record["id"]
        try:
            existing = session.get(Opportunity, opp_id)
            if existing:
                for key, value in record.items():
                    if key != "created_at":
                        setattr(existing, key, value)
                stats["records_updated"] += 1
            else:
                record["created_at"] = datetime.now(timezone.utc).isoformat()
                session.add(Opportunity(**record))
                stats["records_added"] += 1
        except Exception as exc:
            logger.warning("upsert_failed", record_id=opp_id, error=str(exc))
            stats["records_failed"] += 1
    session.flush()


# ─── REST path ─────────────────────────────────────────────────────────────────


def _ingest_via_rest(session) -> dict | None:
    """Fetch opportunities from the Grants.gov REST search2 API.

    Returns a stats dict on success, or None if REST is unavailable/unreliable
    (caller should fall back to XML).
    """
    stats = {
        "source": "grants_gov",
        "status": "success",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    all_records: list[dict] = []
    pages_fetched = 0

    for page in range(MAX_REST_PAGES):
        payload = {
            "keyword": "",
            "oppStatuses": ["forecasted", "posted"],
            "rows": REST_PAGE_SIZE,
            "startRecordNum": page * REST_PAGE_SIZE,
            "sortBy": "openDate|desc",
        }
        try:
            resp = httpx.post(
                SEARCH2_ENDPOINT,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as exc:
            logger.warning("rest_unavailable", connection_error=str(exc))
            return None

        if resp.status_code >= 500:
            logger.warning("rest_unavailable", status=resp.status_code)
            return None

        if resp.status_code >= 400:
            logger.warning("rest_client_error", status=resp.status_code, body=resp.text[:200])
            return None

        try:
            data = resp.json()
        except Exception as exc:
            logger.warning("rest_parse_error", exc=str(exc))
            return None

        opp_data = data.get("data", {})
        opp_hits = opp_data.get("oppHits", [])
        pages_fetched += 1

        if not opp_hits:
            break  # no more pages

        for opp in opp_hits:
            raw_id = opp.get("id")
            if not raw_id:
                continue

            record: dict = {}
            for rest_key, model_key in REST_FIELD_MAP.items():
                raw_val = opp.get(rest_key)
                if model_key in ("post_date", "close_date"):
                    raw_val = normalize_date(str(raw_val) if raw_val else None)
                elif model_key in ("award_ceiling", "award_floor"):
                    try:
                        raw_val = float(raw_val) if raw_val is not None else None
                    except (ValueError, TypeError):
                        raw_val = None
                record[model_key] = raw_val

            # CFDA numbers: REST returns a list
            cfda_list = opp.get("cfdaList", [])
            record["cfda_numbers"] = ", ".join(cfda_list) if cfda_list else None

            # Apply normalizers
            record["eligible_applicants"] = normalize_eligibility_codes(
                record.get("eligible_applicants")
            )
            record["agency_name"] = normalize_agency_name(record.get("agency_name"))
            record["category"] = normalize_category(record.get("category"))
            record["funding_instrument"] = normalize_funding_instrument(
                record.get("funding_instrument")
            )
            floor, ceiling = validate_award_amounts(
                record.get("award_floor"), record.get("award_ceiling")
            )
            record["award_floor"] = floor
            record["award_ceiling"] = ceiling

            # Composite id — same format as XML path for deduplication
            record["id"] = f"grants_gov_{raw_id}"
            record["source"] = "grants_gov"
            record["source_url"] = f"https://www.grants.gov/search-results-detail/{raw_id}"
            record["updated_at"] = now_iso
            record["raw_data"] = json.dumps({k: opp.get(k) for k in opp})

            all_records.append(record)

        # Stop if we've exhausted the result set
        total_count = opp_data.get("totalOpportunityCount", 0)
        if (page + 1) * REST_PAGE_SIZE >= total_count:
            break

    records_processed = len(all_records)
    if records_processed < MIN_REST_THRESHOLD:
        logger.warning(
            "rest_below_threshold",
            records=records_processed,
            threshold=MIN_REST_THRESHOLD,
        )
        return None

    # Upsert in batches of 500
    batch_size = 500
    for i in range(0, len(all_records), batch_size):
        _upsert_batch(session, all_records[i : i + batch_size], stats)

    session.commit()

    stats["records_processed"] = records_processed
    stats["extra"] = json.dumps({"path": "rest", "pages_fetched": pages_fetched})

    logger.info(
        "rest_succeeded",
        records=records_processed,
        pages=pages_fetched,
        added=stats["records_added"],
        updated=stats["records_updated"],
    )
    return stats


# ─── XML path ──────────────────────────────────────────────────────────────────


def _find_extract_url() -> str:
    """Find the most recent XML extract zip URL from Grants.gov."""
    # Try direct URL patterns for recent dates
    today = datetime.now(timezone.utc)
    for days_back in range(7):
        date = today - timedelta(days=days_back)
        date_str = date.strftime("%Y%m%d")
        for version in ("v2", "v1", ""):
            suffix = version if version else ""
            filename = f"GrantsDBExtract{date_str}{suffix}.zip"
            url = f"https://prod-grants-gov-chatbot.s3.amazonaws.com/extracts/{filename}"
            try:
                resp = httpx.head(url, follow_redirects=True, timeout=10)
                if resp.status_code == 200:
                    logger.info("Found extract at %s", url)
                    return url
            except httpx.HTTPError:
                continue

    # Fallback: scrape the XML extract page for download links
    logger.info("Trying to scrape %s for download links", GRANTS_GOV_XML_URL)
    resp = httpx.get(GRANTS_GOV_XML_URL, follow_redirects=True, timeout=30)
    resp.raise_for_status()
    # Look for zip file links
    urls = re.findall(r'href=["\']([^"\']*GrantsDBExtract[^"\']*\.zip)["\']', resp.text)
    if urls:
        url = urls[0]
        if not url.startswith("http"):
            url = "https://www.grants.gov" + url
        return url

    raise RuntimeError("Could not find Grants.gov XML extract download URL")


def _download_extract(url: str) -> Path:
    """Download the zip file to DATA_DIR, return the path."""
    filename = url.rsplit("/", 1)[-1]
    filepath = DATA_DIR / filename
    if filepath.exists():
        logger.info("Using cached download: %s", filepath)
        return filepath

    logger.info("Downloading %s ...", url)
    with httpx.stream("GET", url, follow_redirects=True, timeout=300) as resp:
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                f.write(chunk)
    logger.info("Downloaded %s (%.1f MB)", filepath.name, filepath.stat().st_size / 1e6)
    return filepath


def _parse_element(elem: ET.Element) -> dict:
    """Parse an OpportunitySynopsisDetail element into a dict."""
    raw = {}
    record = {}
    for child in elem:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        value = (child.text or "").strip() if child.text else None
        raw[tag] = value

        if tag in DATE_FIELDS:
            value = normalize_date(value)
        elif tag in FLOAT_FIELDS:
            try:
                value = float(value) if value else None
            except (ValueError, TypeError):
                value = None
        elif tag in INT_FIELDS:
            try:
                value = int(value) if value else None
            except (ValueError, TypeError):
                value = None
        elif tag in BOOL_FIELDS:
            if value:
                value = value.lower() in ("yes", "true", "1", "y")
            else:
                value = None

        mapped = FIELD_MAP.get(tag)
        if mapped:
            record[mapped] = value

    record["raw_data"] = json.dumps(raw)

    # Apply normalizers to cooked fields
    record["eligible_applicants"] = normalize_eligibility_codes(
        record.get("eligible_applicants")
    )
    record["agency_name"] = normalize_agency_name(record.get("agency_name"))
    record["category"] = normalize_category(record.get("category"))
    record["funding_instrument"] = normalize_funding_instrument(
        record.get("funding_instrument")
    )
    floor, ceiling = validate_award_amounts(
        record.get("award_floor"), record.get("award_ceiling")
    )
    record["award_floor"] = floor
    record["award_ceiling"] = ceiling

    return record


def _ingest_via_xml(session) -> dict | None:
    """Download, parse, and ingest the Grants.gov XML bulk extract.

    Returns a stats dict on success, or None if the XML path also fails.
    """
    stats = {
        "source": "grants_gov",
        "status": "success",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
    }

    try:
        url = _find_extract_url()
        zip_path = _download_extract(url)

        # Unzip and find the XML file
        xml_path = None
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.endswith(".xml"):
                    xml_path = DATA_DIR / name
                    if not xml_path.exists():
                        zf.extract(name, DATA_DIR)
                    break
        if not xml_path or not xml_path.exists():
            raise RuntimeError("No XML file found in zip archive")

        logger.info("Parsing %s ...", xml_path.name)

        # Parse XML iteratively to handle large files
        now_iso = datetime.now(timezone.utc).isoformat()
        batch = []
        batch_size = 500

        context = ET.iterparse(str(xml_path), events=("end",))
        for event, elem in context:
            # Match elements ending with OpportunitySynopsisDetail or similar
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag not in (
                "OpportunitySynopsisDetail",
                "OpportunitySynopsisDetail_1_0",
                "OpportunityForecastDetail",
                "OpportunityForecastDetail_1_0",
            ):
                continue

            record = _parse_element(elem)
            source_id = record.get("source_id")
            if not source_id:
                elem.clear()
                continue

            opp_id = f"grants_gov_{source_id}"
            record["id"] = opp_id
            record["source"] = "grants_gov"
            record["source_url"] = f"https://www.grants.gov/search-results-detail/{source_id}"
            record["updated_at"] = now_iso

            batch.append(record)
            stats["records_processed"] += 1

            if len(batch) >= batch_size:
                _upsert_batch(session, batch, stats)
                batch = []

            elem.clear()

        # Final batch
        if batch:
            _upsert_batch(session, batch, stats)

        session.commit()

        stats["extra"] = json.dumps({"path": "xml"})
        logger.info(
            "xml_succeeded",
            records=stats["records_processed"],
            added=stats["records_added"],
            updated=stats["records_updated"],
        )
        return stats

    except Exception as exc:
        logger.warning("xml_path_failed", error=str(exc))
        return None


# ─── Public entry point ────────────────────────────────────────────────────────


def ingest_grants_gov() -> dict:
    """Ingest Grants.gov opportunities using REST-first, XML-fallback strategy.

    Returns a stats dict with status, record counts, and the path used.
    """
    stats = {
        "source": "grants_gov",
        "status": "error",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
    }
    started_at = datetime.now(timezone.utc).isoformat()

    session = SessionLocal()
    log_entry = IngestionLog(
        source="grants_gov",
        started_at=started_at,
        status="running",
    )
    session.add(log_entry)
    session.commit()

    try:
        if GRANTS_GOV_USE_REST:
            # Force REST-only mode (config flag for testing/migration validation)
            logger.info("mode=rest_only (GRANTS_GOV_USE_REST=true)")
            rest_stats = _ingest_via_rest(session)
            if rest_stats is None:
                stats["status"] = "error"
                stats["error"] = "REST API unavailable and REST-only mode is set"
            else:
                stats.update(rest_stats)
        else:
            # Try REST first
            logger.info("mode=rest_first attempting REST API")
            rest_stats = _ingest_via_rest(session)

            if rest_stats is not None:
                logger.info(
                    "rest_succeeded",
                    records=rest_stats["records_processed"],
                    path="rest",
                )
                stats.update(rest_stats)
            else:
                # REST unavailable or returned too few records — fall back to XML
                logger.info("rest_fallback", reason="REST returned None, using XML extract")
                xml_stats = _ingest_via_xml(session)
                if xml_stats is not None:
                    stats.update(xml_stats)
                else:
                    stats["status"] = "error"
                    stats["error"] = "Both REST and XML paths failed"

    except Exception as e:
        logger.exception("Grants.gov ingestion failed: %s", e)
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
