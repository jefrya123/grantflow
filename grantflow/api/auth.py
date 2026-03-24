"""API key authentication dependency for FastAPI endpoints."""
import hashlib
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from grantflow.database import get_db, SessionLocal
from grantflow.models import ApiKey

# Daily request limits per tier
TIER_LIMITS = {
    "free": 1000,
    "starter": 10000,
    "growth": 100000,
}

# Module-level session factory — tests may replace this with a test factory.
_session_factory = SessionLocal


def _lookup_tier(key: str) -> str:
    """Hash key and look up its tier in the DB. Returns 'free' if not found."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = _session_factory()
    try:
        row = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
            .first()
        )
        return row.tier if row and row.tier else "free"
    finally:
        db.close()


def _tier_limit(key: str) -> str:
    """slowapi callable: returns per-day rate limit string for the given raw API key.

    slowapi passes the key_func result (which is the raw API key string from the
    X-API-Key header) as the ``key`` argument when the parameter is named ``key``.
    """
    tier = _lookup_tier(key)
    daily = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    return f"{daily}/day"


def _tier_export_limit(key: str) -> str:
    """slowapi callable: export limit is 1/10th of the standard tier limit."""
    tier = _lookup_tier(key)
    daily = TIER_LIMITS.get(tier, TIER_LIMITS["free"])
    return f"{daily // 10}/day"


async def get_api_key(
    x_api_key: str | None = Header(None),
    db: Session = Depends(get_db),
) -> ApiKey:
    """FastAPI dependency that validates X-API-Key header.

    Raises:
        HTTPException 401 MISSING_API_KEY: if header is absent or empty
        HTTPException 401 INVALID_API_KEY: if key hash not found or inactive
    Returns:
        ApiKey: the matching active row from api_keys table
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": "MISSING_API_KEY",
                "message": "API key required. Pass X-API-Key header.",
            },
        )

    key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()

    api_key = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
        .first()
    )

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error_code": "INVALID_API_KEY",
                "message": "API key not found or inactive.",
            },
        )

    # Update usage tracking
    api_key.last_used_at = datetime.now(timezone.utc).isoformat()
    api_key.request_count = (api_key.request_count or 0) + 1
    db.commit()

    return api_key
