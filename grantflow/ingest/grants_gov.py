"""Download and parse the Grants.gov XML bulk extract."""

import json
import logging
import re
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import httpx

from grantflow.config import DATA_DIR, GRANTS_GOV_XML_URL
from grantflow.database import SessionLocal, engine
from grantflow.models import Opportunity, IngestionLog

logger = logging.getLogger(__name__)

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


def _normalize_date(value: str | None) -> str | None:
    """Convert MM/DD/YYYY to YYYY-MM-DD."""
    if not value:
        return None
    for fmt in ("%m%d%Y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


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
            value = _normalize_date(value)
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
    return record


def ingest_grants_gov() -> dict:
    """Download, parse, and ingest the Grants.gov XML extract. Returns stats dict."""
    stats = {
        "source": "grants_gov",
        "status": "error",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
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

        stats["status"] = "success"
        logger.info(
            "Grants.gov ingestion complete: %d processed, %d added, %d updated",
            stats["records_processed"],
            stats["records_added"],
            stats["records_updated"],
        )

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


def _upsert_batch(session, batch: list[dict], stats: dict) -> None:
    """Upsert a batch of opportunity records."""
    for record in batch:
        opp_id = record["id"]
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
    session.flush()
