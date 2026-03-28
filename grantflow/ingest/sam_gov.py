"""Incremental ingest of SAM.gov contract/grant opportunities."""

import json
import time
from datetime import datetime, timezone, timedelta

import httpx

from grantflow.config import SAM_GOV_API_KEY, SAM_GOV_API_BASE
from grantflow.database import SessionLocal
from grantflow.normalizers import (
    normalize_date,
    normalize_eligibility_codes,
    normalize_agency_name,
    normalize_funding_instrument,
    validate_award_amounts,
)
from grantflow.models import Opportunity, IngestionLog, PipelineRun
from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("sam_gov")

SEARCH_ENDPOINT = f"{SAM_GOV_API_BASE}/search"
PAGE_SIZE = 10  # conservative — 10 records per API call
MAX_PAGES = 50  # hard cap: 50 pages × 10 records = 500 records max per run
RATE_LIMIT_PAUSE = 1.0  # seconds between requests


def ingest_sam_gov() -> dict:
    """Incrementally fetch SAM.gov opportunities since last successful run.

    Returns a stats dict with keys:
        status, records_processed, records_added, records_updated,
        records_failed, error
    """
    stats = {
        "source": "sam_gov",
        "status": "error",
        "records_processed": 0,
        "records_added": 0,
        "records_updated": 0,
        "records_failed": 0,
        "error": None,
    }

    # Guard: skip if no API key configured
    if not SAM_GOV_API_KEY:
        logger.warning(
            "sam_gov_api_key_missing",
            msg="SAM_GOV_API_KEY not set — skipping SAM.gov ingestion",
        )
        stats["status"] = "skipped"
        return stats

    started_at = datetime.now(timezone.utc)
    started_at_iso = started_at.isoformat()

    session = SessionLocal()

    # Write IngestionLog entry (health endpoint compatibility)
    log_entry = IngestionLog(
        source="sam_gov",
        started_at=started_at_iso,
        status="running",
    )
    session.add(log_entry)

    # Write PipelineRun entry
    pipeline_run = PipelineRun(
        source="sam_gov",
        run_type="incremental",
        status="running",
        started_at=started_at_iso,
    )
    session.add(pipeline_run)
    session.commit()

    rate_limited = False

    try:
        # Determine modified_since: use last successful run minus 1-day buffer
        last_run = (
            session.query(PipelineRun)
            .filter(
                PipelineRun.source == "sam_gov",
                PipelineRun.status == "success",
            )
            .order_by(PipelineRun.id.desc())
            .first()
        )

        if last_run and last_run.completed_at:
            try:
                last_completed = datetime.fromisoformat(last_run.completed_at)
                modified_since = last_completed - timedelta(days=1)
            except ValueError:
                modified_since = datetime.now(timezone.utc) - timedelta(days=30)
        else:
            # First run: 30-day lookback to stay within rate limits
            modified_since = datetime.now(timezone.utc) - timedelta(days=30)

        logger.info(
            "sam_gov_ingest_start",
            modified_since=modified_since.strftime("%m/%d/%Y"),
            lookback_days=(datetime.now(timezone.utc) - modified_since).days,
        )

        params = {
            "api_key": SAM_GOV_API_KEY,
            "postedFrom": modified_since.strftime("%m/%d/%Y"),
            "postedTo": datetime.now(timezone.utc).strftime("%m/%d/%Y"),
            "ptype": "o",  # solicitations/contracts
            "limit": PAGE_SIZE,
            "offset": 0,
        }

        for page_num in range(MAX_PAGES):
            params["offset"] = page_num * PAGE_SIZE

            resp = httpx.get(SEARCH_ENDPOINT, params=params, timeout=30)

            if resp.status_code == 429:
                logger.warning(
                    "sam_gov_rate_limit_hit",
                    page=page_num,
                    records_fetched=stats["records_processed"],
                )
                rate_limited = True
                break  # stop cleanly — commit what we have

            resp.raise_for_status()
            data = resp.json()
            records = data.get("opportunitiesData", [])

            if not records:
                break  # no more data

            now_iso = datetime.now(timezone.utc).isoformat()

            for record in records:
                notice_id = record.get("noticeId")
                if not notice_id:
                    stats["records_failed"] += 1
                    continue

                opp_id = f"sam_gov_{notice_id}"
                stats["records_processed"] += 1

                # Build agency name from path (use last segment)
                full_path = record.get("fullParentPathName", "")
                agency_name = full_path.split("|")[-1].strip() if full_path else ""

                opp_data = {
                    "id": opp_id,
                    "source": "sam_gov",
                    "source_id": notice_id,
                    "title": record.get("title", ""),
                    "opportunity_number": record.get("solicitationNumber", ""),
                    "agency_name": agency_name,
                    "agency_code": record.get("organizationCode", ""),
                    "post_date": normalize_date(record.get("postedDate")),
                    "close_date": normalize_date(record.get("responseDeadLine")),
                    "opportunity_status": "posted"
                    if record.get("active") == "Yes"
                    else "closed",
                    "description": record.get("description", ""),
                    "funding_instrument": record.get("type", ""),
                    "cfda_numbers": record.get("naicsCode", ""),
                    "eligible_applicants": record.get("typeOfSetAside", ""),
                    "raw_data": json.dumps(record),
                    "updated_at": now_iso,
                }

                # Normalize through shared pipeline (consistent with grants_gov.py, sbir.py, usaspending.py)
                opp_data["eligible_applicants"] = normalize_eligibility_codes(
                    opp_data.get("eligible_applicants")
                )
                opp_data["agency_name"] = normalize_agency_name(
                    opp_data.get("agency_name")
                )
                opp_data["funding_instrument"] = normalize_funding_instrument(
                    opp_data.get("funding_instrument")
                )
                floor, ceiling = validate_award_amounts(
                    opp_data.get("award_floor"), opp_data.get("award_ceiling")
                )
                opp_data["award_floor"] = floor
                opp_data["award_ceiling"] = ceiling

                existing = session.get(Opportunity, opp_id)
                if existing:
                    for key, value in opp_data.items():
                        if key != "created_at":
                            setattr(existing, key, value)
                    stats["records_updated"] += 1
                else:
                    opp_data["created_at"] = now_iso
                    session.add(Opportunity(**opp_data))
                    stats["records_added"] += 1

            session.flush()

            logger.info(
                "sam_gov_page_fetched",
                page=page_num + 1,
                records_on_page=len(records),
                total_processed=stats["records_processed"],
            )

            # Respectful pacing between requests
            time.sleep(RATE_LIMIT_PAUSE)

        session.commit()

        # Partial success if rate-limited but got some records
        if rate_limited:
            stats["status"] = "partial"
        else:
            stats["status"] = "success"

        logger.info(
            "sam_gov_ingest_complete",
            status=stats["status"],
            records_processed=stats["records_processed"],
            records_added=stats["records_added"],
            records_updated=stats["records_updated"],
            rate_limited=rate_limited,
        )

    except Exception as e:
        logger.exception("sam_gov_ingest_failed", error=str(e))
        stats["status"] = "error"
        stats["error"] = str(e)
        session.rollback()

    finally:
        completed_at = datetime.now(timezone.utc).isoformat()

        # Update IngestionLog
        log_entry.completed_at = completed_at
        log_entry.records_processed = stats["records_processed"]
        log_entry.records_added = stats["records_added"]
        log_entry.records_updated = stats["records_updated"]
        log_entry.status = stats["status"]
        log_entry.error = stats.get("error")

        # Update PipelineRun
        pipeline_run.completed_at = completed_at
        pipeline_run.status = stats["status"]
        pipeline_run.records_processed = stats["records_processed"]
        pipeline_run.records_added = stats["records_added"]
        pipeline_run.records_updated = stats["records_updated"]
        pipeline_run.records_failed = stats["records_failed"]
        pipeline_run.error_message = stats.get("error")
        pipeline_run.extra = json.dumps({"rate_limited": rate_limited})

        try:
            session.commit()
        except Exception:
            session.rollback()
        session.close()

    return stats
