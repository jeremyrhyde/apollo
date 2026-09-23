"""The object graph the API routes use, built once by main.build_services()."""

from __future__ import annotations

from dataclasses import dataclass

from config import Settings
from core.events import EventBus
from core.state import Database
from services.calendar import CalendarService
from services.catalog import Catalog
from services.clock import Clock
from services.selfcare import SelfcareService
from services.workouts import WorkoutService


@dataclass
class Services:
    settings: Settings
    catalog: Catalog
    clock: Clock
    db: Database
    bus: EventBus
    workouts: WorkoutService
    selfcare: SelfcareService
    calendar: CalendarService
