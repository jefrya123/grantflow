"""
Weekly email digest for saved search alerts.

Matches new opportunities against active SavedSearches and sends
plain-text digest emails to subscribers.
"""

import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from sqlalchemy.orm import Session

from grantflow.api.query import build_opportunity_query
from grantflow.models import Opportunity, SavedSearch


def match_saved_search(db: Session, search: SavedSearch, since: str) -> list[Opportunity]:
    """Return opportunities matching the saved search posted on or after `since` (YYYY-MM-DD)."""
    query = build_opportunity_query(
        db,
        q=search.query,
        agency=search.agency_code,
        category=search.category,
        eligible=search.eligible_applicants,
        min_award=search.min_award,
        max_award=search.max_award,
    )
    query = query.filter(Opportunity.post_date >= since)
    return query.all()


def render_digest(search: SavedSearch, opportunities: list[Opportunity]) -> str:
    """Return plain-text email body for the digest."""
    lines = [
        f'Hello,',
        f'',
        f'Here are new grants matching your saved search "{search.name}":',
        f'',
    ]
    for opp in opportunities:
        lines.append(f'- {opp.title}')
        if opp.agency_name:
            lines.append(f'  Agency: {opp.agency_name}')
        if opp.close_date:
            lines.append(f'  Deadline: **{opp.close_date}**')
        url = opp.source_url or getattr(opp, 'additional_info_url', None)
        if url:
            lines.append(f'  Link: {url}')
        lines.append('')
    lines.append(
        'To unsubscribe, log in to GrantFlow and delete this saved search.'
    )
    return '\n'.join(lines)


def send_digest_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text digest email via SMTP_SSL."""
    from grantflow.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER

    msg = MIMEText(body, 'plain')
    msg['Subject'] = subject
    msg['From'] = SMTP_FROM
    msg['To'] = to

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.sendmail(SMTP_FROM, [to], msg.as_string())


def send_weekly_digests(db: Session) -> None:
    """Loop active SavedSearches, send digest if new matches, update last_alerted_at."""
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime('%Y-%m-%d')
    active_searches = (
        db.query(SavedSearch).filter(SavedSearch.is_active.is_(True)).all()
    )

    for search in active_searches:
        opps = match_saved_search(db, search, since)
        if not opps:
            continue

        subject = f'GrantFlow: {len(opps)} new grant(s) for "{search.name}"'
        body = render_digest(search, opps)
        send_digest_email(search.alert_email, subject, body)

        search.last_alerted_at = datetime.now(timezone.utc).isoformat()
        db.commit()
