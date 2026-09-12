"""ZozaFactory FastAPI entrypoint. Production only — no publishing surface."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import configure_logging, get_logger

log = get_logger("zoza-factory")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    init_db()
    from app.modules.reality_assets import acquisition as assets_mod
    from app.core.database import get_session_factory
    db = get_session_factory()()
    try:
        assets_mod.seed_catalog(db)
    finally:
        db.close()
    try:
        from app.services import creator_os as cos
        cos.heartbeat()
    except Exception:
        pass
    log.info("startup factory=%s version=%s env=%s",
             settings.app_name, settings.app_version, settings.environment)
    yield
    log.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version,
                  lifespan=lifespan,
                  description="Autonomous production factory: Pulse decides WHAT, Zoza decides HOW. Never publishes.")
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health/live")
    def live():
        return {"status": "ok", "service": "zoza-factory"}

    @app.get("/health/ready")
    def ready():
        try:
            init_db()
            return {"ready": True, "service": "zoza-factory"}
        except Exception as exc:
            return JSONResponse(status_code=503,
                                content={"ready": False, "error": str(exc)[:200]})

    return app


app = create_app()
