"""API key issuance endpoint."""

import hashlib
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from grantflow.database import get_db
from grantflow.models import ApiKey
from grantflow.api.schemas import KeyCreateResponse

router = APIRouter(prefix="/api/v1")

VALID_TIERS = {"free", "starter", "growth"}


@router.post("/keys", response_model=KeyCreateResponse)
def create_api_key(
    body: dict | None = None, db: Session = Depends(get_db)
) -> KeyCreateResponse:
    """Generate a new API key. The plaintext key is returned exactly once and never stored."""
    body = body or {}
    tier = body.get("tier", "free")

    if tier not in VALID_TIERS:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "INVALID_TIER",
                "message": "tier must be one of: free, starter, growth",
            },
        )

    # Generate secure random key
    plaintext_key = "gf_" + secrets.token_urlsafe(32)
    key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
    key_prefix = plaintext_key[:8]  # covers "gf_" + 5 chars
    created_at = datetime.now(timezone.utc).isoformat()

    api_key = ApiKey(
        key_hash=key_hash,
        key_prefix=key_prefix,
        tier=tier,
        is_active=True,
        created_at=created_at,
        request_count=0,
    )
    db.add(api_key)
    db.commit()

    return KeyCreateResponse(
        key=plaintext_key,
        key_prefix=key_prefix,
        tier=tier,
        created_at=created_at,
    )
