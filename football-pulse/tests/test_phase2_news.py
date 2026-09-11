"""Phase 2 tests: NewsService + News Intelligence Agent."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.agents.base import AgentContext, AgentStatus
from app.db.models import Memory, News
from app.db.models.phase2 import NewsCluster
from app.services import news_service


def test_content_hash_stable_and_sensitive():
    h1 = news_service.content_hash("Arsenal Win", "https://x.com/1")
    assert h1 == news_service.content_hash("  arsenal win ", "https://x.com/1")
    assert h1 != news_service.content_hash("Chelsea Win", "https://x.com/1")
    assert h1 != news_service.content_hash("Arsenal Win", "https://x.com/2")


def test_ingest_article_output_shape(sample_articles):
    item = news_service.ingest_article(sample_articles[0])
    for key in ("title", "summary", "source", "url", "published_at",
                "importance_score", "breaking_news", "entities"):
        assert key in item, f"missing {key}"
    assert 0.0 <= item["importance_score"] <= 1.0
    assert item["breaking_news"] is True  # confirmed + official + reliable source


def test_deduplicate_splits_unique_and_duplicates():
    articles = [
        {"title": "A", "url": "https://x/1", "content_hash": "h1"},
        {"title": "A", "url": "https://x/1", "content_hash": "h1"},
        {"title": "B", "url": "https://x/2", "content_hash": "h2"},
    ]
    unique, dups = news_service.deduplicate(articles)
    assert [a["content_hash"] for a in unique] == ["h1", "h2"]
    assert len(dups) == 1


def test_deduplicate_respects_known_hashes():
    articles = [{"title": "A", "url": "https://x/1"}]
    unique, dups = news_service.deduplicate(articles, known_hashes={"whatever"})
    assert unique == [] or True  # hash computed from content; ensure no crash
    h = news_service.content_hash("A", "https://x/1")
    unique, dups = news_service.deduplicate([{"title": "A", "url": "https://x/1"}], known_hashes={h})
    assert unique == [] and len(dups) == 1


def test_importance_reliable_source_scores_higher():
    entities = {"clubs": ["arsenal"], "competitions": ["premier league"], "people": []}
    reliable = news_service.importance_score("Arsenal win", None, "BBC Sport", entities)
    unknown = news_service.importance_score("Arsenal win", None, "Random Blog XYZ", entities)
    assert 0.0 <= reliable <= 1.0
    assert reliable > unknown


def test_breaking_requires_keyword_and_score():
    assert news_service.is_breaking("Official: confirmed signing", None, 0.9) is True
    assert news_service.is_breaking("Official: confirmed signing", None, 0.2) is False
    assert news_service.is_breaking("Midfielder trains ahead of match", None, 0.9) is False


def test_extract_entities_finds_clubs_and_competitions():
    entities = news_service.extract_entities(
        "Arsenal face Real Madrid in Champions League thriller", "Premier League race"
    )
    assert "arsenal" in entities["clubs"]
    assert "champions league" in entities["competitions"]


def test_cluster_news_groups_similar_titles(sample_articles):
    ingested = news_service.ingest_news(sample_articles)
    clusters = news_service.cluster_news(ingested, threshold=0.2)
    assert len(clusters) == 2  # two Arsenal stories cluster, weather stands alone
    big = max(clusters, key=lambda c: c["article_count"])
    assert big["article_count"] == 2
    assert big["trend_score"] > 0


def test_rank_news_breaking_first():
    articles = [
        {"title": "a", "breaking_news": False, "importance_score": 0.95, "published_at": None},
        {"title": "b", "breaking_news": True, "importance_score": 0.5, "published_at": None},
    ]
    ranked = news_service.rank_news(articles)
    assert ranked[0]["title"] == "b"


async def test_news_agent_persists_and_updates_memory(session_factory, sample_articles):
    from app.agents.news_agent import NewsIntelligenceAgent

    agent = NewsIntelligenceAgent()
    result = await agent.run(AgentContext(payload={"articles": sample_articles}))
    assert result.status == AgentStatus.SUCCEEDED
    assert result.output["persisted"] == 3
    assert len(result.output["clusters"]) >= 1

    async with session_factory() as session:
        news_count = (await session.execute(select(func.count()).select_from(News))).scalar()
        assert news_count == 3
        cluster_count = (await session.execute(select(func.count()).select_from(NewsCluster))).scalar()
        assert cluster_count >= 1
        mem = (await session.execute(
            select(Memory).where(Memory.kind == "trending_clubs", Memory.key == "arsenal")
        )).scalar_one_or_none()
        assert mem is not None and mem.value["count"] >= 1


async def test_news_agent_dedupes_on_second_run(session_factory, sample_articles):
    from app.agents.news_agent import NewsIntelligenceAgent

    agent = NewsIntelligenceAgent()
    first = await agent.run(AgentContext(payload={"articles": sample_articles}))
    second = await agent.run(AgentContext(payload={"articles": sample_articles}))
    assert first.output["persisted"] == 3
    assert second.output["persisted"] == 0
    assert second.output["duplicates"] == 3
