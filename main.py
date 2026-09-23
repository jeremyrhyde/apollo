"""Apollo entry point.

`python main.py` (make run, the background service) builds the app and serves
it. `make run-dev` uses uvicorn's factory mode: `uvicorn --factory main:build_app`.
There is deliberately no module-level `app`, so importing this module (tests)
has no side effects.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI

from config import Settings
from core.api import create_app
from core.container import Services
from core.events import EventBus
from core.state import Database
from services import preferences
from services.calendar import CalendarService
from services.catalog import load_catalog
from services.clock import Clock
from services.selfcare import SelfcareService
from services.workouts import WorkoutService

logger = logging.getLogger("apollo")


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def build_services(settings: Settings, now_fn: Callable[[], datetime] | None = None) -> Services:
    catalog = load_catalog(settings.CONFIG_DIR)
    for error in catalog.errors:
        logger.error("config: %s", error)
    db = Database(settings.DB_PATH)
    db.migrate()
    apollo = catalog.apollo
    clock = Clock(apollo.timezone, apollo.day_start_hour, now_fn)
    bus = EventBus()
    preferences.seed(db, apollo.settings_defaults, clock.now_iso())
    return Services(
        settings=settings,
        catalog=catalog,
        clock=clock,
        db=db,
        bus=bus,
        workouts=WorkoutService(db, catalog, clock, bus, apollo.stale_workout_hours),
        selfcare=SelfcareService(db, catalog, clock, bus),
        calendar=CalendarService(db, catalog),
    )


def build_app(settings: Settings | None = None, now_fn: Callable[[], datetime] | None = None) -> FastAPI:
    settings = settings or Settings()
    _configure_logging(settings.LOG_LEVEL)
    services = build_services(settings, now_fn)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        services.db.close()

    return create_app(services, lifespan=lifespan)


if __name__ == "__main__":
    s = Settings()
    uvicorn.run(build_app(s), host=s.HOST, port=s.PORT, log_level=s.LOG_LEVEL)
