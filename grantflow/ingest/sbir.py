"""Download and parse SBIR award data and solicitations."""

import csv
import hashlib
import io
import json
import logging  # noqa: F401 — kept for any stdlib callers
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

from grantflow.config import DATA_DIR, SBIR_AWARDS_CSV_URL, SBIR_SOLICITATIONS_API
from grantflow.database import SessionLocal
from grantflow.models import Award, Opportunity, IngestionLog
from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("sbir")

# Minimum year for awards (last 3 years)
MIN_AWARD_YEAR = datetime.now(timezone.utc).year - 3

# CSV field mapping: csv_field -> model_field
CSV_FIELD_MAP = {
    "firm": "recipient_name",
    "award_title": "title",
    "award_amount": "award_amount",
    "agency": "agency_name",
    "phase": "award_type",
    "proposal_award_date": "award_date",
    "state": "place_state",
    "city": "place_city",
    "abstract": "description",
}


def _parse_date(value: str | None) -> str | None:
    """Try parsing various date formats to ISO 8601."""
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S", "%m/%d/%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return value


def _make_award_key(row: dict) -> str:
    """Generate a unique key for an SBIR award row."""
    # Combine multiple fields for uniqueness
    parts = [
        row.get("agency", ""),
        row.get("firm", ""),
        row.get("proposal_award_date", ""),
        row.get("award_title", "")[:50] if row.get("award_title") else "",
        row.get("contract", "") or row.get("award_number", "") or "",
    ]
    key = hashlib.md5("|".join(parts).encode()).hexdigest()[:16]
    return key


def _download_csv() -> Path:
    """Download the SBIR awards CSV to DATA_DIR, streaming to disk."""
    filepath = DATA_DIR / "sbir_award_data.csv"

    # Re-download if older than 24 hours or doesn't exist
    if filepath.exists():
        age = datetime.now().timestamp() - filepath.stat().st_mtime
        if age < 86400:
            logger.info("Using cached SBIR CSV: %s", filepath)
            return filepath

    logger.info("Downloading SBIR awards CSV (this may take a while) ...")
    with httpx.stream("GET", SBIR_AWARDS_CSV_URL, follow_redirects=True, timeout=600) as resp:
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=1024 * 256):
                f.write(chunk)

    logger.info("Downloaded SBIR CSV (%.1f MB)", filepath.stat().st_size / 1e6)
    return filepath


def _ingest_awards(session, stats: dict) -> None:
    """Parse the CSV and ingest recent awards."""
    csv_path = _download_csv()
    now_iso = datetime.now(timezone.utc).isoformat()

    logger.info("Parsing SBIR awards CSV ...")
    batch_count = 0

    with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter to recent years
            award_year = row.get("award_year") or ""
            proposal_date = row.get("proposal_award_date") or ""

            # Try award_year first
            try:
                year = int(award_year)
                if year < MIN_AWARD_YEAR:
                    continue
            except (ValueError, TypeError):
                # Try extracting year from date
                parsed = _parse_date(proposal_date)
                if parsed:
                    try:
                        year = int(parsed[:4])
                        if year < MIN_AWARD_YEAR:
                            continue
                    except (ValueError, TypeError):
                        continue
                else:
                    continue

            key = _make_award_key(row)
            record_id = f"sbir_{key}"

            # Parse amount
            amount = row.get("award_amount")
            if amount:
                try:
                    amount = float(amount.replace(",", "").replace("$", ""))
                except (ValueError, TypeError):
                    amount = None

            record = {
                "id": record_id,
                "source": "sbir",
                "award_id": key,
                "title": row.get("award_title", ""),
                "description": row.get("abstract", ""),
                "agency_name": row.get("agency", ""),
                "recipient_name": row.get("firm", ""),
                "award_amount": amount,
                "award_date": _parse_date(proposal_date),
                "place_state": row.get("state", ""),
                "place_city": row.get("city", ""),
                "award_type": row.get("phase", ""),
                "raw_data": json.dumps({k: v for k, v in row.items() if v}),
            }

            stats["records_processed"] += 1

            existing = session.get(Award, record_id)
            if existing:
                for k, v in record.items():
                    if k != "created_at":
                        setattr(existing, k, v)
                stats["records_updated"] += 1
            else:
                record["created_at"] = now_iso
                session.add(Award(**record))
                stats["records_added"] += 1

            batch_count += 1
            if batch_count % 1000 == 0:
                session.flush()
                logger.info("SBIR awards: %d processed so far ...", stats["records_processed"])

    session.flush()


def _ingest_solicitations(session, stats: dict) -> None:
    """Fetch active SBIR solicitations and store as opportunities."""
    logger.info("Fetching SBIR solicitations ...")
    now_iso = datetime.now(timezone.utc).isoformat()

    last_exc = None
    for attempt in range(3):
        try:
            resp = httpx.get(
                SBIR_SOLICITATIONS_API,
                params={"rows": 50},
                follow_redirects=True,
                timeout=30,
            )
            resp.raise_for_status()
            break
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_exc = e
            logger.warning("sbir_solicitations_fetch_retry", attempt=attempt + 1, error=str(e))
            if attempt < 2:
                time.sleep(2 ** attempt)
    else:
        logger.error("sbir_solicitations_fetch_failed", error=str(last_exc))
        return

    try:
        data = resp.json()
    except Exception as e:
        logger.warning("sbir_solicitations_parse_failed", error=str(e))
        return

    # The API may return a list or a dict with a results key
    if isinstance(data, dict):
        items = data.get("results", data.get("data", []))
    elif isinstance(data, list):
        items = data
    else:
        logger.warning("Unexpected SBIR solicitations response format")
        return

    sol_count = 0
    for item in items:
        sol_id = item.get("solicitation_id") or item.get("id") or ""
        if not sol_id:
            continue

        sol_id = str(sol_id).strip()
        opp_id = f"sbir_{sol_id}"

        close_date = _parse_date(item.get("close_date") or item.get("application_due_date"))
        open_date = _parse_date(item.get("open_date") or item.get("post_date"))

        today = datetime.now(timezone.utc).date().isoformat()
        opportunity_status = "closed" if (close_date and close_date < today) else "posted"

        record = {
            "id": opp_id,
            "source": "sbir",
            "source_id": sol_id,
            "title": item.get("solicitation_title") or item.get("title", ""),
            "description": item.get("description") or item.get("abstract", ""),
            "agency_name": item.get("agency") or "",
            "agency_code": item.get("agency") or "",
            "close_date": close_date,
            "post_date": open_date,
            "opportunity_status": opportunity_status,
            "category": "SBIR/STTR",
            "source_url": item.get("solicitation_url") or item.get("url", ""),
            "additional_info_url": item.get("solicitation_url") or item.get("url", ""),
            "raw_data": json.dumps(item, default=str),
            "updated_at": now_iso,
        }

        existing = session.get(Opportunity, opp_id)
        if existing:
            for k, v in record.items():
                if k != "created_at":
                    setattr(existing, k, v)
        else:
            record["created_at"] = now_iso
            session.add(Opportunity(**record))

        sol_count += 1

    session.flush()
    logger.info("Ingested %d SBIR solicitations", sol_count)


def ingest_sbir() -> dict:
    """Download and ingest SBIR awards and solicitations. Returns stats dict."""
    stats = {
        "source": "sbir",
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
        source="sbir",
        started_at=started_at,
        status="running",
    )
    session.add(log_entry)
    session.commit()

    try:
        _ingest_awards(session, stats)
        _ingest_solicitations(session, stats)
        session.commit()
        stats["status"] = "success"
        logger.info(
            "SBIR ingestion complete: %d processed, %d added, %d updated",
            stats["records_processed"],
            stats["records_added"],
            stats["records_updated"],
        )

    except Exception as e:
        logger.exception("SBIR ingestion failed: %s", e)
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
