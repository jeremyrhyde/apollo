"""HTTP surface: everything under /api, the built UI at /ui.

One `_build_<area>_router()` per area. Domain errors map to their status with
the message as `detail`. Values cross the API in display units; conversion
happens here, at the edge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from core.container import Services
from services.errors import AppError


def _svc(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def _build_health_router() -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health(request: Request) -> dict[str, Any]:
        s = _svc(request)
        errors = list(s.catalog.errors)
        return {"status": "degraded" if errors else "ok", "config_errors": errors}

    return router


def create_app(services: Services, *, lifespan: Any = None, mount_static: bool = True) -> FastAPI:
    app = FastAPI(title="Apollo", lifespan=lifespan)
    app.state.services = services

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    api = APIRouter(prefix="/api")
    api.include_router(_build_health_router())
    app.include_router(api)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    web_dir = Path(services.settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=web_dir, html=True), name="ui")

    return app
