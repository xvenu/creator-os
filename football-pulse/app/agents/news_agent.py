"""News Intelligence Agent: ingest → dedupe → score → cluster → persist → memory."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select

from app.agents.base import AgentContext, AgentMetadata, BaseAgent
from app.core.logging import get_logger
from app.db.models import News
from app.db.models.phase2 import NewsCluster
from app.services import memory_service, news_service

log = get_logger("agent.news_intelligence")

_session_factory: Callable | None = None


def set_session_factory(factory: Callable | None) -> None:
    global _session_factory
    _session_factory = factory


def _resolve_factory() -> Callable:
    if _session_factory is not None:
        return _session_factory
    from app.core.config import get_settings
    from app.db.session import get_session_factory

    return get_session_factory(get_settings())


class NewsIntelligenceAgent(BaseAgent):
    metadata = AgentMetadata(
        name="news_intelligence",
        description="Collect, deduplicate, rank and detect breaking football news",
        version="0.2.0",
    )

    async def handle(self, ctx: AgentContext) -> dict:
        raw_articles: list[dict] = list(ctx.payload.get("articles", []))
        if not raw_articles:
            return {"ingested": 0, "persisted": 0, "duplicates": 0, "items": [], "clusters": []}

        ingested = news_service.ingest_news(raw_articles)
        factory = _resolve_factory()
        async with factory() as session:
            known = set((await session.execute(select(News.content_hash))).scalars().all())
            unique, duplicates = news_service.deduplicate(ingested, known_hashes=known)

            persisted_ids: list[str] = []
            for item in unique:
                row = News(
                    source=item["source"],
                    source_url=item["url"],
                    title=item["title"],
                    body=item["summary"],
                    content_hash=item["content_hash"],
                    importance_score=item["importance_score"],
                    is_breaking=item["breaking_news"],
                    published_at=item["published_at"],
                    meta={"entities": item["entities"]},
                )
                session.add(row)
                await session.flush()
                item["id"] = row.id
                persisted_ids.append(str(row.id))
                await memory_service.observe_entities(session, item["entities"])
            await session.commit()

            clusters = news_service.cluster_news(unique)
            cluster_out: list[dict] = []
            for c in clusters:
                row = NewsCluster(
                    title=c["title"],
                    story_key=c["story_key"],
                    article_count=c["article_count"],
                    trend_score=c["trend_score"],
                    importance_score=c["importance_score"],
                    is_breaking=c["is_breaking"],
                    article_ids=c["article_hashes"],
                    entities=c["entities"],
                    meta={"source_count": c["source_count"]},
                )
                session.add(row)
                await session.flush()
                cluster_out.append({**c, "id": str(row.id)})
            await session.commit()

        ranked = news_service.rank_news(unique)
        log.info(
            "news_intelligence_done",
            ingested=len(ingested),
            persisted=len(unique),
            duplicates=len(duplicates),
            clusters=len(cluster_out),
        )
        return {
            "ingested": len(ingested),
            "persisted": len(unique),
            "duplicates": len(duplicates),
            "items": [
                {
                    "title": a["title"],
                    "summary": a["summary"],
                    "source": a["source"],
                    "url": a["url"],
                    "published_at": a["published_at"].isoformat() if a["published_at"] else None,
                    "importance_score": a["importance_score"],
                    "breaking_news": a["breaking_news"],
                    "entities": a["entities"],
                }
                for a in ranked
            ],
            "clusters": cluster_out,
        }
