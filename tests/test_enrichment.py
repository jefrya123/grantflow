"""
Tests for LLM topic enrichment (Plan 07-02).

All tests use mocked LLM — no real OpenAI API calls.
"""
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grantflow.models import Opportunity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_opportunity(db_session, opp_id: str, topic_tags: str | None = None) -> Opportunity:
    opp = Opportunity(
        id=opp_id,
        source="test",
        source_id=opp_id,
        title=f"Test Opportunity {opp_id}",
        description="A test grant for enrichment testing.",
        topic_tags=topic_tags,
    )
    db_session.add(opp)
    db_session.commit()
    db_session.refresh(opp)
    return opp


# ---------------------------------------------------------------------------
# test_tag_opportunity_mock
# ---------------------------------------------------------------------------

def test_tag_opportunity_mock():
    """tag_single() returns a (opp_id, TopicTags) tuple using mocked OpenAI."""
    from grantflow.enrichment.tagger import tag_single, TopicTags

    fake_tags = TopicTags(topics=["health", "research"], sector="Health")

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=fake_tags)

    with patch("grantflow.enrichment.tagger.instructor") as mock_instructor:
        mock_instructor.from_provider.return_value = mock_client

        result_id, result_tags = asyncio.run(
            tag_single("opp-1", "Health Research Grant", "Funding for health research.")
        )

    assert result_id == "opp-1"
    assert isinstance(result_tags, TopicTags)
    assert len(result_tags.topics) > 0


# ---------------------------------------------------------------------------
# test_topic_filter
# ---------------------------------------------------------------------------

def test_topic_filter(client, db_session):
    """Opportunity with topic_tags='["health","research"]' appears when ?topic=health."""
    _make_opportunity(db_session, "health-opp-1", topic_tags='["health", "research"]')

    resp = client.get(
        "/api/v1/opportunities/search?topic=health",
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = [r["id"] for r in data["results"]]
    assert "health-opp-1" in ids


# ---------------------------------------------------------------------------
# test_topic_filter_excludes
# ---------------------------------------------------------------------------

def test_topic_filter_excludes(client, db_session):
    """Opportunity with topic_tags='["education"]' does NOT appear when ?topic=health."""
    _make_opportunity(db_session, "edu-opp-1", topic_tags='["education"]')

    resp = client.get(
        "/api/v1/opportunities/search?topic=health",
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    ids = [r["id"] for r in data["results"]]
    assert "edu-opp-1" not in ids


# ---------------------------------------------------------------------------
# test_enrichment_skips_without_key
# ---------------------------------------------------------------------------

def test_enrichment_skips_without_key(monkeypatch):
    """run_enrichment() returns early (no error) when OPENAI_API_KEY is unset."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    from grantflow.enrichment.run_enrichment import run_enrichment

    # Should not raise; should return without calling DB or LLM
    run_enrichment()


# ---------------------------------------------------------------------------
# test_enrichment_batch_limit
# ---------------------------------------------------------------------------

def test_enrichment_batch_limit(db_session, monkeypatch):
    """run_enrichment() queries at most ENRICHMENT_BATCH_SIZE records."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake-key")
    monkeypatch.setenv("ENRICHMENT_BATCH_SIZE", "2")

    # Insert 5 un-tagged opportunities
    for i in range(5):
        opp = Opportunity(
            id=f"batch-opp-{i}",
            source="test",
            source_id=f"batch-opp-{i}",
            title=f"Batch Opportunity {i}",
            description="Testing batch limit.",
            topic_tags=None,
        )
        db_session.add(opp)
    db_session.commit()

    from grantflow.enrichment.tagger import TopicTags

    fake_tags = TopicTags(topics=["technology"], sector="Technology")
    processed_ids: list[str] = []

    async def mock_tag_batch(records):
        for r in records:
            processed_ids.append(r["id"])
        return [(r["id"], fake_tags) for r in records]

    with patch("grantflow.enrichment.run_enrichment.tag_batch", mock_tag_batch), \
         patch("grantflow.enrichment.run_enrichment.SessionLocal", return_value=db_session):
        from grantflow.enrichment import run_enrichment as run_enrichment_module
        import importlib
        importlib.reload(run_enrichment_module)
        from grantflow.enrichment.run_enrichment import run_enrichment
        run_enrichment()

    assert len(processed_ids) <= 2
