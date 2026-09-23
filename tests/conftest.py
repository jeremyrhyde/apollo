"""Shared fixtures: a fixed test catalog, a controllable clock, and a fresh DB.

The test catalog is deliberately small and independent of config/ so
changing the shipped starter catalog never breaks tests.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.events import EventBus
from core.state import Database
from services.catalog import load_catalog
from services.clock import Clock

TEST_APOLLO = """
timezone: America/Los_Angeles
day_start_hour: 4
colors: {workout: "#4ade80", selfcare: "#60a5fa"}
settings_defaults: {calendar_view: month, week_start: monday, weight_unit: lb, distance_unit: mi, history_range: 1M}
stale_workout_hours: 12
"""

TEST_EXERCISES = """
metric_types:
  weight_reps:   {fields: [weight, reps]}
  reps:          {fields: [reps]}
  time:          {fields: [duration]}
  distance_time: {fields: [distance, duration]}
muscle_groups: [chest, back, legs, glutes, core, cardio]
exercises:
  - {key: bench_press, name: Bench Press, group: chest, type: weight_reps}
  - {key: barbell_row, name: Barbell Row, group: back, type: weight_reps}
  - {key: squat, name: Back Squat, groups: [legs, glutes], type: weight_reps}
  - {key: pull_up, name: Pull-up, group: back, type: reps}
  - {key: plank, name: Plank, group: core, type: time}
  - {key: run, name: Run, group: cardio, type: distance_time}
"""

TEST_SELFCARE = """
categories:
  - key: skincare
    name: Skincare (Face)
    types:
      - {key: am_routine, name: AM routine, every_days: 1}
      - {key: exfoliation, name: Exfoliation, every_days: 7}
      - {key: face_mask, name: Face mask}
"""


class FakeNow:
    """Callable clock source; move time with `advance()` or assign `.dt`."""

    def __init__(self, dt: datetime) -> None:
        self.dt = dt

    def __call__(self) -> datetime:
        return self.dt

    def advance(self, **kwargs: float) -> None:
        self.dt += timedelta(**kwargs)


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    d = tmp_path / "config"
    d.mkdir()
    (d / "apollo.yaml").write_text(TEST_APOLLO)
    (d / "exercises.yaml").write_text(TEST_EXERCISES)
    (d / "selfcare.yaml").write_text(TEST_SELFCARE)
    return d


@pytest.fixture
def now() -> FakeNow:
    # 2026-09-22 18:00 UTC = 11:00 PDT → local date 2026-09-22
    return FakeNow(datetime(2026, 9, 22, 18, 0, tzinfo=UTC))


@pytest.fixture
def env(tmp_path: Path, config_dir: Path, now: FakeNow):
    catalog = load_catalog(config_dir)
    assert catalog.errors == ()
    db = Database(str(tmp_path / "test.db"))
    db.migrate()
    clock = Clock(catalog.apollo.timezone, catalog.apollo.day_start_hour, now)
    yield SimpleNamespace(catalog=catalog, db=db, clock=clock, bus=EventBus(), now=now)
    db.close()
