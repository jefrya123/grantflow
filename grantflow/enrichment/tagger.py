"""
LLM-powered topic tagging for grant opportunities.

Uses instructor + OpenAI gpt-4o-mini to classify opportunities into
predefined topic/sector buckets. All calls are async for batch efficiency.
"""

import asyncio

import instructor
from pydantic import BaseModel

TOPICS = [
    "health",
    "research",
    "education",
    "environment",
    "housing",
    "small_business",
    "agriculture",
    "transportation",
    "defense",
    "arts",
    "justice",
    "technology",
    "community_development",
    "ada-compliance",
]

_SYSTEM_PROMPT = (
    "You are a grant classification assistant. "
    "Given a grant title and description, assign the most relevant topic tags "
    f"from this list: {', '.join(TOPICS)}. "
    "Also provide the primary sector as a short label. "
    "Return only 1-3 topic tags that best match."
)


class TopicTags(BaseModel):
    topics: list[str]
    sector: str


async def tag_single(
    opp_id: str, title: str, description: str
) -> tuple[str, TopicTags]:
    """
    Classify a single opportunity using gpt-4o-mini via instructor.

    Returns (opp_id, TopicTags).
    """
    client = instructor.from_provider("openai", async_client=True)
    content = f"Title: {title}\n\nDescription: {description or ''}"
    tags: TopicTags = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_model=TopicTags,
    )
    return (opp_id, tags)


async def tag_batch(records: list[dict]) -> list[tuple[str, TopicTags]]:
    """
    Classify a batch of opportunities concurrently.

    Each record dict must have: id, title, description.
    Concurrency is capped at 10 to avoid OpenAI rate limits.
    """
    semaphore = asyncio.Semaphore(10)

    async def _limited(record: dict) -> tuple[str, TopicTags]:
        async with semaphore:
            return await tag_single(
                record["id"],
                record.get("title", ""),
                record.get("description", ""),
            )

    results = await asyncio.gather(*[_limited(r) for r in records])
    return list(results)
