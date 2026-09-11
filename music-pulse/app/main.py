"""MusicPulse FastAPI entrypoint."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.logging import setup_logging
from app.core.database import init_db
from app.core.plugins import load_plugins
from app.api.routes import router as api_router
from app.api.phase2 import router as phase2_router
from app.api.phase3 import router as phase3_router
from app.api.phase4 import router as phase4_router
from app.api.phase6 import router as phase6_router
from app.api.phase7 import router as phase7_router
from app.api.phase8 import router as phase8_router
from app.admin.views import router as admin_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    load_plugins()
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="MusicPulse", version="0.8.0", lifespan=lifespan,
                    description="Pulse business owner: intelligence → Zoza render → own publishing")
    app.include_router(api_router, prefix="/api")
    app.include_router(phase2_router, prefix="/api/v2")
    app.include_router(phase3_router, prefix="/api/v3")
    app.include_router(phase4_router, prefix="/api/v4")
    app.include_router(phase6_router, prefix="/api/v6")
    app.include_router(phase7_router, prefix="/api/v7")
    app.include_router(phase8_router, prefix="/api/v8")
    app.include_router(admin_router)

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "musicpulse"}

    return app


app = create_app()
