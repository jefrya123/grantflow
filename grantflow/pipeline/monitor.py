"""Pipeline staleness monitoring — detect stale sources and fire alerts."""

import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText

from sqlalchemy import func
from sqlalchemy.orm import Session

from grantflow.database import SessionLocal
from grantflow.models import PipelineRun
from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("monitor")

# Per-source stale thresholds
FEDERAL_STALE_THRESHOLD_HOURS = 48
STATE_STALE_THRESHOLD_HOURS = 240  # 10 days for weekly scrapers

# Backward-compat alias
STALE_THRESHOLD_HOURS = FEDERAL_STALE_THRESHOLD_HOURS

STALE_THRESHOLDS: dict[str, int] = {
    "grants_gov": FEDERAL_STALE_THRESHOLD_HOURS,
    "usaspending": FEDERAL_STALE_THRESHOLD_HOURS,
    "sbir": FEDERAL_STALE_THRESHOLD_HOURS,
    "sam_gov": FEDERAL_STALE_THRESHOLD_HOURS,
    "state_california": STATE_STALE_THRESHOLD_HOURS,
    "state_new_york": STATE_STALE_THRESHOLD_HOURS,
    "state_illinois": STATE_STALE_THRESHOLD_HOURS,
    "state_texas": STATE_STALE_THRESHOLD_HOURS,
    "state_colorado": STATE_STALE_THRESHOLD_HOURS,
}

KNOWN_SOURCES = [
    "grants_gov", "usaspending", "sbir", "sam_gov",
    "state_california", "state_new_york", "state_illinois",
    "state_texas", "state_colorado",
]

# Sources that should be checked for zero-record runs
ZERO_RECORD_SOURCES = [s for s in KNOWN_SOURCES if s.startswith("state_")]


def get_freshness_report(session: Session | None = None) -> dict:
    """Return per-source freshness status.

    Returns a dict keyed by source name with keys:
        status: 'ok' | 'stale' | 'never_run'
        last_success: ISO 8601 string or None
        hours_since: float or None
    """
    own_session = session is None
    if own_session:
        session = SessionLocal()

    try:
        report = {}
        now = datetime.now(timezone.utc)

        for source in KNOWN_SOURCES:
            last_success_ts = session.query(
                func.max(PipelineRun.completed_at)
            ).filter(
                PipelineRun.source == source,
                PipelineRun.status == "success",
            ).scalar()

            if last_success_ts is None:
                report[source] = {
                    "status": "never_run",
                    "last_success": None,
                    "hours_since": None,
                }
                continue

            # Parse ISO 8601 — handle both naive and aware timestamps
            try:
                completed = datetime.fromisoformat(last_success_ts.replace("Z", "+00:00"))
                if completed.tzinfo is None:
                    completed = completed.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                report[source] = {
                    "status": "never_run",
                    "last_success": last_success_ts,
                    "hours_since": None,
                }
                continue

            hours_since = (now - completed).total_seconds() / 3600
            threshold = STALE_THRESHOLDS.get(source, FEDERAL_STALE_THRESHOLD_HOURS)

            if hours_since > threshold:
                status = "stale"
            else:
                status = "ok"

            report[source] = {
                "status": status,
                "last_success": last_success_ts,
                "hours_since": round(hours_since, 1),
            }

        return report

    finally:
        if own_session:
            session.close()


def _send_alert_email(source: str, hours_since: float, last_success: str | None) -> None:
    """Send a plain-text stale-data alert email. Failures are logged, never raised."""
    alert_email = os.environ.get("GRANTFLOW_ALERT_EMAIL")
    if not alert_email:
        return

    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", "25"))

    subject = f"[GrantFlow] Stale data alert: {source}"
    threshold = STALE_THRESHOLDS.get(source, FEDERAL_STALE_THRESHOLD_HOURS)
    body = (
        f"Source {source} has not successfully ingested in {hours_since:.1f} hours "
        f"(threshold: {threshold}h).\n"
        f"Last success: {last_success}. Check pipeline logs."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "grantflow@localhost"
    msg["To"] = alert_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.sendmail("grantflow@localhost", [alert_email], msg.as_string())
        logger.info("stale_alert_email_sent", source=source, recipient=alert_email)
    except Exception as exc:
        logger.error("stale_alert_email_failed", source=source, error=str(exc))


def _send_zero_records_alert(source: str) -> None:
    """Send a zero-records alert email. Failures are logged, never raised."""
    alert_email = os.environ.get("GRANTFLOW_ALERT_EMAIL")
    if not alert_email:
        return

    smtp_host = os.environ.get("SMTP_HOST", "localhost")
    smtp_port = int(os.environ.get("SMTP_PORT", "25"))

    subject = f"[GrantFlow] Zero records alert: {source}"
    body = (
        f"Source {source} last successful run returned 0 records. "
        f"The scraper may be broken or the portal structure may have changed. "
        f"Check pipeline logs."
    )

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = "grantflow@localhost"
    msg["To"] = alert_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as smtp:
            smtp.sendmail("grantflow@localhost", [alert_email], msg.as_string())
        logger.info("zero_records_alert_email_sent", source=source, recipient=alert_email)
    except Exception as exc:
        logger.error("zero_records_alert_email_failed", source=source, error=str(exc))


def check_staleness(session: Session | None = None) -> list[str]:
    """Check all sources for staleness. Logs ERROR and optionally sends email for stale sources.

    Returns:
        List of stale source names. Empty list means all sources are fresh.
    """
    report = get_freshness_report(session)
    stale_sources = []

    for source, info in report.items():
        if info["status"] == "stale":
            threshold = STALE_THRESHOLDS.get(source, FEDERAL_STALE_THRESHOLD_HOURS)
            logger.error(
                "stale_source_detected",
                source=source,
                hours_since=info["hours_since"],
                threshold=threshold,
            )
            _send_alert_email(source, info["hours_since"], info["last_success"])
            stale_sources.append(source)

    return stale_sources


def check_zero_records(session: Session | None = None) -> list[str]:
    """Alert if any state scraper's last successful run returned 0 records.

    Only checks state sources (those in ZERO_RECORD_SOURCES).
    Returns list of broken source names.
    """
    own_session = session is None
    if own_session:
        session = SessionLocal()

    broken = []
    try:
        for source in ZERO_RECORD_SOURCES:
            # Find the most recent successful run for this source
            last_run = (
                session.query(PipelineRun)
                .filter(
                    PipelineRun.source == source,
                    PipelineRun.status == "success",
                )
                .order_by(PipelineRun.completed_at.desc())
                .first()
            )

            if last_run is None:
                # Never run — not a zero-record failure
                continue

            if last_run.records_processed == 0:
                logger.error(
                    "zero_records_detected",
                    source=source,
                    run_id=last_run.id,
                    completed_at=last_run.completed_at,
                )
                _send_zero_records_alert(source)
                broken.append(source)

    finally:
        if own_session:
            session.close()

    return broken
