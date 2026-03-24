"""
CLI entrypoint for LLM topic enrichment.

Processes un-tagged opportunities in configurable batches.
APScheduler integration is explicitly deferred to a future phase.

Usage:
    uv run python -m grantflow.enrichment.run_enrichment
"""
import asyncio
import json
import logging
import os

from grantflow.database import SessionLocal
from grantflow.models import Opportunity
from grantflow.enrichment.tagger import tag_batch

logger = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500


def run_enrichment() -> None:
    """
    Classify un-tagged opportunities with LLM topic tags.

    - Skips silently when OPENAI_API_KEY is not set.
    - Queries at most ENRICHMENT_BATCH_SIZE records (default 500).
    - Commits in sub-batches of 50 to reduce transaction size.
    """
    if not os.getenv("OPENAI_API_KEY"):
        logger.info("OPENAI_API_KEY not set, skipping enrichment")
        return

    batch_size = int(os.getenv("ENRICHMENT_BATCH_SIZE", str(DEFAULT_BATCH_SIZE)))

    db = SessionLocal()
    try:
        rows = (
            db.query(Opportunity)
            .filter(Opportunity.topic_tags.is_(None))
            .limit(batch_size)
            .all()
        )

        if not rows:
            logger.info("No un-tagged opportunities found, skipping enrichment")
            return

        records = [
            {"id": opp.id, "title": opp.title or "", "description": opp.description or ""}
            for opp in rows
        ]

        logger.info("Enriching %d opportunities with topic tags", len(records))
        results = asyncio.run(tag_batch(records))

        # Build a lookup for fast access
        tags_by_id = {opp_id: tags for opp_id, tags in results}

        # Commit in sub-batches of 50
        commit_batch_size = 50
        for i, opp in enumerate(rows):
            tags = tags_by_id.get(opp.id)
            if tags:
                opp.topic_tags = json.dumps(tags.topics)
            if (i + 1) % commit_batch_size == 0:
                db.commit()
                logger.debug("Committed sub-batch up to record %d", i + 1)

        db.commit()
        logger.info("Enrichment complete: tagged %d opportunities", len(results))

    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_enrichment()
