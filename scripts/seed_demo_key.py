"""Idempotent demo API key provisioner.

Creates a 'playground-demo' API key if one does not already exist.
Prints the plaintext key on first creation; prints existing prefix on subsequent runs.

Usage:
    uv run python scripts/seed_demo_key.py
"""
import hashlib
import secrets
from datetime import datetime, timezone

from grantflow.database import SessionLocal, init_db
from grantflow.models import ApiKey

DEMO_KEY_NAME = "playground-demo"
DEMO_KEY_TIER = "free"


def seed_demo_key() -> str | None:
    """Provision a demo API key idempotently. Returns the plaintext key on creation, None if already existed."""
    init_db()

    session = SessionLocal()
    try:
        # Check for existing demo key by prefix that starts with "gf_demo" pattern.
        # We use key_prefix stored in the DB to identify it, combined with a fixed name convention.
        # Since ApiKey has no 'name' column, we use key_prefix starting with "gf_demo" as the marker.
        existing = session.query(ApiKey).filter(
            ApiKey.key_prefix == "gf_demo_p"
        ).first()

        if existing:
            print(f"Demo key already exists.")
            print(f"  prefix: {existing.key_prefix}...")
            print(f"  tier:   {existing.tier}")
            print(f"  active: {existing.is_active}")
            print()
            print("Set GRANTFLOW_DEMO_API_KEY to the full plaintext key (printed on first creation).")
            return None

        # Create a new demo key with a recognizable prefix
        # gf_demo_ prefix makes it easy to identify, followed by random bytes
        random_suffix = secrets.token_urlsafe(24)
        plaintext_key = "gf_demo_p" + random_suffix
        key_hash = hashlib.sha256(plaintext_key.encode()).hexdigest()
        key_prefix = plaintext_key[:8]  # "gf_demo_"... first 8 chars

        demo_key = ApiKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            tier=DEMO_KEY_TIER,
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
            request_count=0,
        )
        session.add(demo_key)
        session.commit()

        print("Demo API key created successfully!")
        print(f"  prefix: {key_prefix}...")
        print(f"  tier:   {DEMO_KEY_TIER}")
        print()
        print(f"Plaintext key (shown once — store securely):")
        print(f"  {plaintext_key}")
        print()
        print("Export for playground use:")
        print(f'  export GRANTFLOW_DEMO_API_KEY="{plaintext_key}"')
        return plaintext_key
    finally:
        session.close()


if __name__ == "__main__":
    seed_demo_key()
