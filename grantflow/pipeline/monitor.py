"""Pipeline staleness monitoring — detect stale sources and fire alerts."""

import os
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText

from sqlalchemy import func
from sqlalchemy.orm import Session

from grantflow.database import SessionLocal
from grantflow.models import PipelineRun
from grantflow.pipeline.logging import bind_source_logger

logger = bind_source_logger("monitor")

STALE_THRESHOLD_HOURS = 48
KNOWN_SOURCES = ["grants_gov", "usaspending", "sbir", "sam_gov"]


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

            if hours_since > STALE_THRESHOLD_HOURS:
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
    body = (
        f"Source {source} has not successfully ingested in {hours_since:.1f} hours "
        f"(threshold: 48h).\n"
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


def check_staleness(session: Session | None = None) -> list[str]:
    """Check all sources for staleness. Logs ERROR and optionally sends email for stale sources.

    Returns:
        List of stale source names. Empty list means all sources are fresh.
    """
    report = get_freshness_report(session)
    stale_sources = []

    for source, info in report.items():
        if info["status"] == "stale":
            logger.error(
                "stale_source_detected",
                source=source,
                hours_since=info["hours_since"],
                threshold=STALE_THRESHOLD_HOURS,
            )
            _send_alert_email(source, info["hours_since"], info["last_success"])
            stale_sources.append(source)

    return stale_sources
