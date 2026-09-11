"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.agents import register_all_agents
from app.api.v1.routes.agents import router as agents_router
from app.api.v1.routes.campaigns import router as campaigns_router
from app.api.v1.routes.executive import router as executive_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.matches import router as matches_router
from app.api.v1.routes.news import router as news_router
from app.api.v1.routes.opportunities import router as opportunities_router
from app.api.v1.routes.packages import router as packages_router
from app.api.v1.routes.predictions import router as predictions_router
from app.api.v1.routes.regions import router as regions_router
from app.api.v1.routes.research import router as research_router
from app.api.v1.routes.scripts import router as scripts_router
from app.api.v1.routes.seo import router as seo_router
from app.api.v1.routes.thumbnails import router as thumbnails_router
from app.api.v1.routes.transfers import router as transfers_router
from app.api.v1.routes.zoza import router as zoza_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger

log = get_logger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    log.info("startup", app=settings.app_name, version=settings.app_version, env=settings.environment)
    register_all_agents()
    yield
    log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.log_format)
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.include_router(health_router, prefix=f"{settings.api_prefix}/health")
    app.include_router(agents_router, prefix=f"{settings.api_prefix}/agents")
    app.include_router(news_router, prefix=f"{settings.api_prefix}/news")
    app.include_router(matches_router, prefix=f"{settings.api_prefix}/matches")
    app.include_router(transfers_router, prefix=f"{settings.api_prefix}/transfers")
    app.include_router(campaigns_router, prefix=f"{settings.api_prefix}/campaigns")
    app.include_router(predictions_router, prefix=f"{settings.api_prefix}/predictions")
    app.include_router(opportunities_router, prefix=f"{settings.api_prefix}/opportunities")
    app.include_router(executive_router, prefix=f"{settings.api_prefix}/executive")
    app.include_router(research_router, prefix=f"{settings.api_prefix}/research")
    app.include_router(scripts_router, prefix=f"{settings.api_prefix}/scripts")
    app.include_router(seo_router, prefix=f"{settings.api_prefix}/seo")
    app.include_router(thumbnails_router, prefix=f"{settings.api_prefix}/thumbnails")
    app.include_router(regions_router, prefix=f"{settings.api_prefix}/regions")
    app.include_router(packages_router, prefix=f"{settings.api_prefix}/packages")
    app.include_router(zoza_router, prefix=f"{settings.api_prefix}/zoza")
    return app


app = create_app()
