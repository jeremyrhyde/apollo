# Apollo MVP — Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use subagent-driven-development (recommended) or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Apollo's backend — YAML catalog, SQLite store, workout / self-care / calendar services and the `/api` HTTP surface — fully covered by pytest, ready for the Svelte frontend (separate plan: `2026-09-22-mvp-frontend-plan.md`).

**Architecture:** FastAPI app built by `main.build_app()`. Three YAML files in `config/` are validated into a `Catalog` at boot. A thin `Database` wrapper over stdlib `sqlite3` runs forward-only SQL migrations. Domain logic lives in `services/` (one class per area, SI units internally); `core/api.py` exposes it under `/api` and converts units at the edge.

**Tech Stack:** Python ≥ 3.11, FastAPI, pydantic v2, pydantic-settings, PyYAML, stdlib `sqlite3` + `zoneinfo`, pytest, `uv`.

**Spec:** `docs/2026-09-22-mvp-spec.md` — read §3–§6 and §8–§9 before starting.

### Adjustments to the spec (decided while planning)

1. **stdlib `sqlite3` instead of `aiosqlite`.** Single user, tiny queries; FastAPI runs sync route handlers in a threadpool. A process-wide `RLock` serialises access. Simpler code and tests. (JournalGym, the reference project on this stack, does the same.)
2. **SQL lives in the service modules**, not all in `core/state.py`. `core/state.py` owns the connection, transactions and migrations.
3. **Extra snapshot column** `workout_exercise.metric_fields` (e.g. `"weight,reps"`) so history keeps its field list even if a metric type is later removed from YAML.
4. **One-open-workout index** is `CREATE UNIQUE INDEX … ON workout(ended_at IS NULL) WHERE ended_at IS NULL` (SQLite rejects a constant-expression index).
5. **`GET /api/today`** added so the UI uses the server's notion of today (timezone + day-start hour).
6. **No module-level `app`** in `main.py`; uvicorn uses `--factory main:build_app`, `python main.py` still works. Importing `main` in tests no longer creates `./apollo.db`.
7. Durations cross the API as **seconds**; the UI formats `m:ss`.

### Task order and parallelism

```
1 ─► 2 ─► 3 ─┐
1 ─► 4 ──────┤
1 ─► 5 ──────┼─► 8 ─┐
1 ─► 6 ──────┤      │
1 ─► 7 ──────┴─► 9 ─┼─► 10 ─┐
                    └─► 11 ─┴─► 12 ─► 13 ─► 14
```
Tasks 4, 5, 6, 7 are independent of each other (after 1). 10 and 11 are independent (after 9). Everything else is sequential. Each task owns the files it lists; no two parallel tasks touch the same file.

### File map

| File | Responsibility | Task |
|---|---|---|
| `config.py` | Settings (`CONFIG_DIR`, `WEB_DIR`, `DB_PATH`…) | 1 |
| `schemas/config.py` | pydantic models for the three YAML files | 2 |
| `config/*.yaml` | shipped catalog | 2 |
| `services/catalog.py` | load + validate YAML → `Catalog` | 3 |
| `services/clock.py` | now / today / local dates / ranges | 4 |
| `services/units.py` | SI ↔ display units | 5 |
| `core/state.py`, `core/migrations/001_initial.sql` | connection, transactions, migrations, schema | 6 |
| `services/errors.py`, `core/events.py` | domain errors, event bus | 7 |
| `services/preferences.py` | Settings-tab preferences | 8 |
| `schemas/workouts.py`, `services/workouts.py` | workout lifecycle | 9, 10 |
| `schemas/selfcare.py`, `services/selfcare.py` | self-care sessions + due logic | 11 |
| `schemas/calendar.py`, `services/calendar.py` | calendar merge + last done | 12 |
| `services/metrics.py` | placeholder for stats | 13 |
| `core/container.py`, `core/api.py`, `main.py`, `Makefile` | wiring + HTTP | 13, 14 |
| `tests/conftest.py` | shared fixtures (`config_dir`, `now`, `env`) | 9 (+`client` in 14) |

Run all Python commands from the repo root `~/Development/apollo`.

---

### Task 0: Branch

- [ ] **Step 1: Create the working branch from `template`**

```bash
cd ~/Development/apollo
git checkout template
git checkout -b feat/mvp
```

---

### Task 1: Restructure the skeleton

Remove the Alpine placeholder UI, move the kiosk launcher out of `web/`, and add the settings the rest of the plan needs.

**Files:**
- Move: `web/kiosk/` → `deploy/kiosk/`
- Delete: `web/index.html`, `web/app.js`, `web/style.css`, `web/manifest.webmanifest`, `web/icon.svg`
- Modify: `scripts/install-kiosk.sh`, `deploy/xinitrc.kiosk`, `deploy/kiosk/apollo-kiosk.service`, `deploy/kiosk/start-kiosk.sh` (path strings)
- Modify: `config.py`, `.gitignore`, `README.md`, `tests/test_health.py`

- [ ] **Step 1: Move and delete**

```bash
git mv web/kiosk deploy/kiosk
git rm -q web/index.html web/app.js web/style.css web/manifest.webmanifest web/icon.svg
sed -i '' 's#web/kiosk#deploy/kiosk#g' scripts/install-kiosk.sh deploy/xinitrc.kiosk deploy/kiosk/apollo-kiosk.service deploy/kiosk/start-kiosk.sh
grep -rn "web/kiosk" . --exclude-dir=.git --exclude-dir=.venv || echo "no stale paths"
```
Expected last line: `no stale paths`. (`start-kiosk.sh` finds `.env` two levels up — still correct from `deploy/kiosk/`.)

- [ ] **Step 2: Replace `config.py`**

```python
"""Application configuration loaded from the environment or `.env`.

Field names are uppercase to match environment variables — setting `PORT=9000`
overrides the default. Add every new knob here (and to `.env.example`) rather
than reading `os.environ` at the call site.

Domain configuration (exercises, self-care types, colors, timezone) lives in
the YAML files under CONFIG_DIR, not here; these are deployment settings.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the Apollo server."""

    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"
    WEB_DIR: str = "./frontend/dist"
    DB_PATH: str = "./apollo.db"
    CONFIG_DIR: str = "./config"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
```

- [ ] **Step 3: Update `.env.example`** — replace the line `#WEB_DIR=./web` with:

```
#WEB_DIR=./frontend/dist
#CONFIG_DIR=./config
```

- [ ] **Step 4: Append to `.gitignore`**

```
# Frontend
frontend/node_modules/
frontend/dist/
```

- [ ] **Step 5: Update the README layout block** — in `README.md`, replace the three lines starting `web/ `, `web/kiosk/ ` and `deploy/ ` inside the Layout code block with:

```
config/               apollo.yaml, exercises.yaml, selfcare.yaml — the catalog
frontend/             Svelte 5 + Vite app, built to frontend/dist and served at /ui
deploy/               systemd unit, launchd plist, kiosk/ launcher, headless-X files
```

- [ ] **Step 6: Drop the UI test** — replace `tests/test_health.py` with:

```python
from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_health_ok(tmp_path):
    client = TestClient(build_app(Settings(DB_PATH=str(tmp_path / "t.db"))))
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest -q`
Expected: `1 passed`

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: move kiosk to deploy/, drop placeholder UI, add CONFIG_DIR"
```

---

### Task 2: Config schemas and shipped YAML

**Files:**
- Create: `schemas/config.py`, `config/apollo.yaml`, `config/exercises.yaml`, `config/selfcare.yaml`
- Test: `tests/test_config_schema.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_config_schema.py`

```python
import pytest
from pydantic import ValidationError

from schemas.config import ApolloFile, ExercisesFile, SelfcareFile

EX_OK = {
    "metric_types": {"weight_reps": {"fields": ["weight", "reps"]}, "time": {"fields": ["duration"]}},
    "muscle_groups": ["chest", "legs", "glutes", "core"],
    "exercises": [
        {"key": "bench_press", "name": "Bench Press", "group": "chest", "type": "weight_reps"},
        {"key": "squat", "name": "Squat", "groups": ["legs", "glutes"], "type": "weight_reps"},
        {"key": "plank", "name": "Plank", "group": "core", "type": "time"},
    ],
}


def test_valid_exercises_file():
    f = ExercisesFile.model_validate(EX_OK)
    assert [e.muscle_groups for e in f.exercises] == [["chest"], ["legs", "glutes"], ["core"]]


def test_unknown_top_level_key_rejected():
    with pytest.raises(ValidationError):
        ExercisesFile.model_validate({**EX_OK, "extra": 1})


def test_group_and_groups_are_exclusive():
    bad = {**EX_OK, "exercises": [{"key": "x", "name": "X", "group": "chest", "groups": ["legs"], "type": "time"}]}
    with pytest.raises(ValidationError, match="exactly one of"):
        ExercisesFile.model_validate(bad)


def test_unknown_type_and_group_named():
    bad = {**EX_OK, "exercises": [{"key": "x", "name": "X", "group": "arms", "type": "nope"}]}
    with pytest.raises(ValidationError) as exc:
        ExercisesFile.model_validate(bad)
    assert "unknown type 'nope'" in str(exc.value)
    assert "unknown muscle group 'arms'" in str(exc.value)


def test_duplicate_exercise_key():
    bad = {**EX_OK, "exercises": EX_OK["exercises"] + [EX_OK["exercises"][0]]}
    with pytest.raises(ValidationError, match="duplicate exercise key 'bench_press'"):
        ExercisesFile.model_validate(bad)


def test_bad_field_name_rejected():
    bad = {**EX_OK, "metric_types": {"weird": {"fields": ["speed"]}}}
    with pytest.raises(ValidationError):
        ExercisesFile.model_validate(bad)


def test_key_format_enforced():
    bad = {**EX_OK, "exercises": [{"key": "Bench Press", "name": "B", "group": "chest", "type": "time"}]}
    with pytest.raises(ValidationError, match="lowercase"):
        ExercisesFile.model_validate(bad)


def test_selfcare_every_days_must_be_positive():
    with pytest.raises(ValidationError):
        SelfcareFile.model_validate(
            {"categories": [{"key": "skincare", "name": "S", "types": [{"key": "a", "name": "A", "every_days": 0}]}]}
        )


def test_selfcare_duplicate_type_key():
    with pytest.raises(ValidationError, match="duplicate type key 'a'"):
        SelfcareFile.model_validate(
            {"categories": [{"key": "skincare", "name": "S", "types": [{"key": "a", "name": "A"}, {"key": "a", "name": "B"}]}]}
        )


def test_apollo_defaults_and_validation():
    assert ApolloFile().settings_defaults.calendar_view == "month"
    with pytest.raises(ValidationError, match="unknown timezone"):
        ApolloFile.model_validate({"timezone": "Mars/Olympus"})
    with pytest.raises(ValidationError):
        ApolloFile.model_validate({"colors": {"workout": "green"}})
    with pytest.raises(ValidationError):
        ApolloFile.model_validate({"day_start_hour": 24})
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_config_schema.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'schemas.config'`

- [ ] **Step 3: Implement `schemas/config.py`**

```python
"""Pydantic models for the three YAML files in config/.

Strict on purpose: unknown keys are errors, so a typo in a YAML file is
reported at boot instead of silently ignored. Cross-references (an exercise's
type and muscle groups) are checked here too, and every problem is reported,
not just the first.
"""

from __future__ import annotations

import re
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, PositiveInt, field_validator, model_validator

FieldName = Literal["weight", "reps", "distance", "duration"]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _check_key(value: str) -> str:
    if not KEY_RE.match(value):
        raise ValueError(f"key {value!r} must be lowercase letters, digits and underscores")
    return value


# ------------------------------------------------------------------ exercises


class MetricType(_Strict):
    fields: list[FieldName] = Field(min_length=1)

    @field_validator("fields")
    @classmethod
    def _unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("fields must not repeat")
        return value


class Exercise(_Strict):
    key: str
    name: str = Field(min_length=1)
    group: str | None = None
    groups: list[str] | None = None
    type: str

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return _check_key(value)

    @model_validator(mode="after")
    def _one_group_field(self) -> "Exercise":
        if (self.group is None) == (self.groups is None):
            raise ValueError(f"exercise {self.key!r}: set exactly one of 'group' or 'groups'")
        if self.groups is not None and not self.groups:
            raise ValueError(f"exercise {self.key!r}: 'groups' must not be empty")
        return self

    @property
    def muscle_groups(self) -> list[str]:
        return [self.group] if self.group is not None else list(self.groups or [])


class ExercisesFile(_Strict):
    metric_types: dict[str, MetricType] = {}
    muscle_groups: list[str] = []
    exercises: list[Exercise] = []

    @model_validator(mode="after")
    def _cross_references(self) -> "ExercisesFile":
        errors: list[str] = []
        for key in self.metric_types:
            if not KEY_RE.match(key):
                errors.append(f"metric type key {key!r} must be lowercase letters, digits and underscores")
        if len(set(self.muscle_groups)) != len(self.muscle_groups):
            errors.append("muscle_groups must not repeat")
        seen: set[str] = set()
        for ex in self.exercises:
            if ex.key in seen:
                errors.append(f"duplicate exercise key {ex.key!r}")
            seen.add(ex.key)
            if ex.type not in self.metric_types:
                errors.append(f"exercise {ex.key!r}: unknown type {ex.type!r}")
            for group in ex.muscle_groups:
                if group not in self.muscle_groups:
                    errors.append(f"exercise {ex.key!r}: unknown muscle group {group!r}")
        if errors:
            raise ValueError("; ".join(errors))
        return self


# ------------------------------------------------------------------ self-care


class SelfcareType(_Strict):
    key: str
    name: str = Field(min_length=1)
    every_days: PositiveInt | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return _check_key(value)


class SelfcareCategory(_Strict):
    key: str
    name: str = Field(min_length=1)
    types: list[SelfcareType] = Field(min_length=1)

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return _check_key(value)

    @model_validator(mode="after")
    def _unique_types(self) -> "SelfcareCategory":
        seen: set[str] = set()
        for t in self.types:
            if t.key in seen:
                raise ValueError(f"category {self.key!r}: duplicate type key {t.key!r}")
            seen.add(t.key)
        return self


class SelfcareFile(_Strict):
    categories: list[SelfcareCategory] = []

    @model_validator(mode="after")
    def _unique_categories(self) -> "SelfcareFile":
        keys = [c.key for c in self.categories]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            raise ValueError(f"duplicate category key(s): {', '.join(dupes)}")
        return self


# ------------------------------------------------------------------ apollo.yaml


class SettingsDefaults(_Strict):
    calendar_view: Literal["week", "month", "year"] = "month"
    week_start: Literal["monday", "sunday"] = "monday"
    weight_unit: Literal["lb", "kg"] = "lb"
    distance_unit: Literal["mi", "km"] = "mi"
    history_range: Literal["1W", "1M", "1Y"] = "1M"


class Colors(_Strict):
    workout: str = "#4ade80"
    selfcare: str = "#60a5fa"

    @field_validator("workout", "selfcare")
    @classmethod
    def _hex(cls, value: str) -> str:
        if not HEX_RE.match(value):
            raise ValueError(f"color {value!r} must be #rrggbb")
        return value


class ApolloFile(_Strict):
    timezone: str = "UTC"
    day_start_hour: int = Field(4, ge=0, le=23)
    colors: Colors = Colors()
    settings_defaults: SettingsDefaults = SettingsDefaults()
    stale_workout_hours: PositiveInt = 12

    @field_validator("timezone")
    @classmethod
    def _tz(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value
```

- [ ] **Step 4: Create `config/apollo.yaml`**

```yaml
# Apollo — general configuration. Edits take effect on restart.

# All "today" and local-date decisions use this IANA timezone.
timezone: America/Los_Angeles

# A session before this hour belongs to the previous day (late-night workouts).
day_start_hour: 4

# Per-kind colors used by the calendar and chips. Keep them distinguishable
# for colour-blind viewers and readable on dark and light themes.
colors:
  workout: "#4ade80"
  selfcare: "#60a5fa"

# Seeds the Settings tab on first run only. After that, change them in the app.
settings_defaults:
  calendar_view: month      # week | month | year
  week_start: monday        # monday | sunday
  weight_unit: lb           # lb | kg
  distance_unit: mi         # mi | km
  history_range: 1M         # 1W | 1M | 1Y

# An open workout older than this is flagged so you can finish or discard it.
stale_workout_hours: 12
```

- [ ] **Step 5: Create `config/exercises.yaml`**

```yaml
# Apollo — exercise catalog. Edits take effect on restart.
#
# `key` is permanent: history is tied to it. Change `name` freely.
# Each exercise sets exactly one of `group` or `groups`.
# Fields available to metric types: weight, reps, distance, duration.

metric_types:
  weight_reps:   { fields: [weight, reps] }
  reps:          { fields: [reps] }
  time:          { fields: [duration] }
  distance_time: { fields: [distance, duration] }

muscle_groups: [chest, back, shoulders, biceps, triceps, legs, glutes, core, cardio]

exercises:
  # chest
  - { key: bench_press,           name: Bench Press (Barbell),    group: chest,     type: weight_reps }
  - { key: incline_dumbbell_press, name: Incline Dumbbell Press,  group: chest,     type: weight_reps }
  - { key: push_up,               name: Push-up,                  group: chest,     type: reps }
  # back
  - { key: barbell_row,           name: Barbell Row,              group: back,      type: weight_reps }
  - { key: lat_pulldown,          name: Lat Pulldown,             group: back,      type: weight_reps }
  - { key: pull_up,               name: Pull-up,                  group: back,      type: reps }
  - { key: deadlift,              name: Deadlift,                 groups: [back, legs, glutes], type: weight_reps }
  # shoulders
  - { key: overhead_press,        name: Overhead Press,           group: shoulders, type: weight_reps }
  - { key: lateral_raise,         name: Lateral Raise,            group: shoulders, type: weight_reps }
  # arms
  - { key: bicep_curl,            name: Bicep Curl (Dumbbell),    group: biceps,    type: weight_reps }
  - { key: hammer_curl,           name: Hammer Curl,              group: biceps,    type: weight_reps }
  - { key: tricep_pushdown,       name: Tricep Pushdown,          group: triceps,   type: weight_reps }
  - { key: dip,                   name: Dip,                      groups: [triceps, chest], type: reps }
  # legs
  - { key: squat,                 name: Back Squat,               groups: [legs, glutes], type: weight_reps }
  - { key: leg_press,             name: Leg Press,                group: legs,      type: weight_reps }
  - { key: romanian_deadlift,     name: Romanian Deadlift,        groups: [legs, glutes], type: weight_reps }
  - { key: lunge,                 name: Walking Lunge,            groups: [legs, glutes], type: weight_reps }
  - { key: calf_raise,            name: Calf Raise,               group: legs,      type: weight_reps }
  # core
  - { key: plank,                 name: Plank,                    group: core,      type: time }
  - { key: side_plank,            name: Side Plank,               group: core,      type: time }
  - { key: hanging_leg_raise,     name: Hanging Leg Raise,        group: core,      type: reps }
  # cardio
  - { key: run,                   name: Run,                      group: cardio,    type: distance_time }
  - { key: stair_climb,           name: Stair Climber,            group: cardio,    type: distance_time }
  - { key: cycle,                 name: Cycling,                  group: cardio,    type: distance_time }
  - { key: row_erg,               name: Rowing Machine,           group: cardio,    type: distance_time }
```

- [ ] **Step 6: Create `config/selfcare.yaml`**

```yaml
# Apollo — self-care catalog. Edits take effect on restart.
#
# `every_days` is optional. With it, the type appears in the Due list
# (due N days after it was last done). Without it, it is tracked only.

categories:
  - key: skincare
    name: Skincare (Face)
    types:
      - { key: am_routine,  name: AM routine,  every_days: 1 }
      - { key: pm_routine,  name: PM routine,  every_days: 1 }
      - { key: exfoliation, name: Exfoliation, every_days: 7 }
      - { key: face_mask,   name: Face mask,   every_days: 7 }
      - { key: retinoid,    name: Retinoid,    every_days: 3 }
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/test_config_schema.py -q`
Expected: `10 passed`

- [ ] **Step 8: Commit**

```bash
git add schemas/config.py config/ tests/test_config_schema.py
git commit -m "feat: config schemas and starter catalog"
```

---

### Task 3: Catalog loader

**Files:**
- Create: `services/catalog.py`
- Test: `tests/test_catalog.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_catalog.py`

```python
from pathlib import Path

from services.catalog import load_catalog

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config"


def _write(d: Path, apollo: str = "", exercises: str = "", selfcare: str = "") -> Path:
    d.mkdir(exist_ok=True)
    (d / "apollo.yaml").write_text(apollo)
    (d / "exercises.yaml").write_text(exercises)
    (d / "selfcare.yaml").write_text(selfcare)
    return d


EXERCISES = """
metric_types: {weight_reps: {fields: [weight, reps]}, time: {fields: [duration]}}
muscle_groups: [chest, legs, glutes, core]
exercises:
  - {key: bench_press, name: Bench, group: chest, type: weight_reps}
  - {key: squat, name: Squat, groups: [legs, glutes], type: weight_reps}
  - {key: plank, name: Plank, group: core, type: time}
"""

SELFCARE = """
categories:
  - key: skincare
    name: Skincare (Face)
    types: [{key: am_routine, name: AM routine, every_days: 1}]
"""


def test_repo_config_is_valid():
    catalog = load_catalog(REPO_CONFIG)
    assert catalog.errors == ()
    assert catalog.exercise("bench_press") is not None


def test_lookups(tmp_path):
    c = load_catalog(_write(tmp_path / "c", exercises=EXERCISES, selfcare=SELFCARE))
    assert c.errors == ()
    assert c.exercise("squat").name == "Squat"
    assert c.exercise("nope") is None
    assert c.fields_for("weight_reps") == ["weight", "reps"]
    by_group = c.exercises_by_group()
    assert list(by_group) == ["chest", "legs", "glutes", "core"]
    assert [e.key for e in by_group["glutes"]] == ["squat"]
    assert c.category("skincare").name == "Skincare (Face)"
    assert c.selfcare_type("skincare", "am_routine").every_days == 1
    assert c.selfcare_type("skincare", "nope") is None


def test_empty_files_fall_back_to_defaults(tmp_path):
    c = load_catalog(_write(tmp_path / "c"))
    assert c.errors == ()
    assert c.apollo.timezone == "UTC"
    assert c.exercises.exercises == []


def test_missing_file_reported(tmp_path):
    d = _write(tmp_path / "c", exercises=EXERCISES)
    (d / "selfcare.yaml").unlink()
    c = load_catalog(d)
    assert c.errors == ("selfcare.yaml: file not found",)
    assert c.selfcare.categories == []


def test_invalid_file_reported_with_location_and_others_still_load(tmp_path):
    bad = EXERCISES.replace("type: time", "type: nope")
    c = load_catalog(_write(tmp_path / "c", exercises=bad, selfcare=SELFCARE))
    assert len(c.errors) == 1
    assert c.errors[0].startswith("exercises.yaml: ")
    assert "unknown type 'nope'" in c.errors[0]
    assert c.exercises.exercises == []          # the broken file falls back to empty
    assert c.category("skincare") is not None   # the good ones still load


def test_yaml_syntax_error_reported(tmp_path):
    c = load_catalog(_write(tmp_path / "c", apollo="timezone: [unclosed"))
    assert c.errors[0].startswith("apollo.yaml: ")


def test_non_mapping_top_level_reported(tmp_path):
    c = load_catalog(_write(tmp_path / "c", apollo="- a list"))
    assert c.errors == ("apollo.yaml: top level must be a mapping",)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_catalog.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.catalog'`

- [ ] **Step 3: Implement `services/catalog.py`**

```python
"""Load and validate the YAML catalog in CONFIG_DIR.

Every file is loaded independently. A file that is missing or invalid is
reported in `Catalog.errors` (surfaced at /api/health and in Settings) and
replaced by its empty default, so one bad file never takes the server down or
hides the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

from schemas.config import (
    ApolloFile,
    Exercise,
    ExercisesFile,
    SelfcareCategory,
    SelfcareFile,
    SelfcareType,
)


@dataclass(frozen=True)
class Catalog:
    apollo: ApolloFile
    exercises: ExercisesFile
    selfcare: SelfcareFile
    errors: tuple[str, ...] = ()

    def exercise(self, key: str) -> Exercise | None:
        return next((e for e in self.exercises.exercises if e.key == key), None)

    def fields_for(self, metric_type: str) -> list[str]:
        return list(self.exercises.metric_types[metric_type].fields)

    def exercises_by_group(self) -> dict[str, list[Exercise]]:
        """Exercises under each muscle group, in muscle_groups order.

        An exercise with several groups appears under each of them.
        """
        out: dict[str, list[Exercise]] = {g: [] for g in self.exercises.muscle_groups}
        for ex in self.exercises.exercises:
            for group in ex.muscle_groups:
                out[group].append(ex)
        return out

    def category(self, key: str) -> SelfcareCategory | None:
        return next((c for c in self.selfcare.categories if c.key == key), None)

    def selfcare_type(self, category_key: str, type_key: str) -> SelfcareType | None:
        cat = self.category(category_key)
        if cat is None:
            return None
        return next((t for t in cat.types if t.key == type_key), None)


_FILES: dict[str, tuple[str, type[BaseModel]]] = {
    "apollo": ("apollo.yaml", ApolloFile),
    "exercises": ("exercises.yaml", ExercisesFile),
    "selfcare": ("selfcare.yaml", SelfcareFile),
}


def _describe(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts = []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            msg = err["msg"].removeprefix("Value error, ")
            parts.append(f"{loc}: {msg}" if loc else msg)
        return "; ".join(parts)
    return str(exc).replace("\n", " ")


def load_catalog(config_dir: str | Path) -> Catalog:
    errors: list[str] = []
    parsed: dict[str, BaseModel] = {}
    for attr, (filename, model) in _FILES.items():
        path = Path(config_dir) / filename
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
            if raw is None:
                raw = {}
            if not isinstance(raw, dict):
                raise ValueError("top level must be a mapping")
            parsed[attr] = model.model_validate(raw)
        except FileNotFoundError:
            errors.append(f"{filename}: file not found")
            parsed[attr] = model()
        except (yaml.YAMLError, ValidationError, ValueError) as exc:
            errors.append(f"{filename}: {_describe(exc)}")
            parsed[attr] = model()
    return Catalog(errors=tuple(errors), **parsed)  # type: ignore[arg-type]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add services/catalog.py tests/test_catalog.py
git commit -m "feat: load and validate the YAML catalog"
```

---

### Task 4: Clock

**Files:**
- Create: `services/clock.py`
- Test: `tests/test_clock.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_clock.py`

```python
from datetime import UTC, date, datetime

import pytest

from services.clock import Clock, from_iso, to_iso

LA = "America/Los_Angeles"


def clock_at(iso: str, tz: str = LA, start: int = 4) -> Clock:
    return Clock(tz, start, now_fn=lambda: datetime.fromisoformat(iso))


def test_today_before_and_after_day_start():
    # 2026-09-22 03:59 PDT (UTC-7) → still the 21st
    assert clock_at("2026-09-22T10:59:00+00:00").today() == date(2026, 9, 21)
    # 04:00 PDT → the 22nd
    assert clock_at("2026-09-22T11:00:00+00:00").today() == date(2026, 9, 22)


def test_day_start_zero_is_midnight():
    assert clock_at("2026-09-22T07:00:00+00:00", start=0).today() == date(2026, 9, 22)


def test_dst_spring_forward():
    # 2026-03-08 10:30Z = 03:30 PDT, the morning clocks jumped; minus 4h → the 7th
    assert clock_at("2026-03-08T10:30:00+00:00").today() == date(2026, 3, 7)


def test_now_is_utc_and_naive_rejected():
    assert clock_at("2026-09-22T11:00:00+00:00").now().tzinfo == UTC
    with pytest.raises(ValueError):
        Clock(LA, 4, now_fn=lambda: datetime(2026, 1, 1)).now()


def test_local_noon_utc():
    c = clock_at("2026-09-22T18:00:00+00:00")
    noon = c.local_noon_utc(date(2026, 9, 20))
    assert noon == datetime(2026, 9, 20, 19, 0, tzinfo=UTC)
    assert c.local_date_of(noon) == date(2026, 9, 20)


def test_range_start():
    c = clock_at("2026-09-22T18:00:00+00:00")
    assert c.range_start("1W") == date(2026, 9, 16)
    assert c.range_start("1M") == date(2026, 8, 24)
    assert c.range_start("1Y") == date(2025, 9, 23)
    with pytest.raises(KeyError):
        c.range_start("2W")


def test_iso_round_trip():
    dt = datetime(2026, 9, 22, 18, 0, 5, tzinfo=UTC)
    assert to_iso(dt) == "2026-09-22T18:00:05+00:00"
    assert from_iso(to_iso(dt)) == dt
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_clock.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.clock'`

- [ ] **Step 3: Implement `services/clock.py`**

```python
"""Every date decision in Apollo goes through here.

"Today" is the local date in the configured timezone, shifted back by
`day_start_hour`, so a workout at 1 a.m. counts on the day it belongs to.
Timestamps are stored as UTC ISO-8601 strings; `to_iso`/`from_iso` are the
only conversions.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

RANGE_DAYS = {"1W": 7, "1M": 30, "1Y": 365}


def to_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat(timespec="seconds")


def from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


class Clock:
    def __init__(
        self,
        timezone: str,
        day_start_hour: int,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.tz = ZoneInfo(timezone)
        self.day_start_hour = day_start_hour
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

    def now(self) -> datetime:
        current = self._now_fn()
        if current.tzinfo is None:
            raise ValueError("now_fn must return an aware datetime")
        return current.astimezone(UTC)

    def now_iso(self) -> str:
        return to_iso(self.now())

    def local_date_of(self, dt: datetime) -> date:
        return (dt.astimezone(self.tz) - timedelta(hours=self.day_start_hour)).date()

    def today(self) -> date:
        return self.local_date_of(self.now())

    def local_noon_utc(self, day: date) -> datetime:
        """The UTC instant of 12:00 local on `day` — used for backdated entries."""
        return datetime(day.year, day.month, day.day, 12, tzinfo=self.tz).astimezone(UTC)

    def range_start(self, range_key: str) -> date:
        """First local date included in a 1W / 1M / 1Y window ending today."""
        return self.today() - timedelta(days=RANGE_DAYS[range_key] - 1)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_clock.py -q`
Expected: `7 passed`

- [ ] **Step 5: Commit**

```bash
git add services/clock.py tests/test_clock.py
git commit -m "feat: clock with timezone and day-start hour"
```

---

### Task 5: Units

**Files:**
- Create: `services/units.py`
- Test: `tests/test_units.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_units.py`

```python
import pytest

from services.units import STORAGE_COLUMNS, UnitPrefs, from_storage, to_storage

LB = UnitPrefs(weight_unit="lb", distance_unit="mi")
KG = UnitPrefs(weight_unit="kg", distance_unit="km")


def test_weight_round_trip_lb():
    kg = to_storage("weight", 135, LB)
    assert kg == pytest.approx(61.2349, abs=1e-4)
    assert from_storage("weight", kg, LB) == 135.0


def test_weight_kg_is_identity():
    assert to_storage("weight", 60, KG) == 60.0
    assert from_storage("weight", 60.0, KG) == 60.0


def test_distance():
    assert to_storage("distance", 3.1, LB) == pytest.approx(4988.97, abs=0.01)
    assert from_storage("distance", 5000.0, LB) == 3.107
    assert to_storage("distance", 5, KG) == 5000.0
    assert from_storage("distance", 5000.0, KG) == 5.0


def test_reps_and_duration():
    assert to_storage("reps", 8, LB) == 8
    assert to_storage("reps", 8.0, LB) == 8
    with pytest.raises(ValueError):
        to_storage("reps", 8.5, LB)
    assert to_storage("duration", 59.6, LB) == 60
    assert from_storage("duration", 60, LB) == 60


def test_none_passes_through():
    for field in STORAGE_COLUMNS:
        assert to_storage(field, None, LB) is None
        assert from_storage(field, None, LB) is None


def test_unknown_field():
    with pytest.raises(KeyError):
        to_storage("speed", 1, LB)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_units.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.units'`

- [ ] **Step 3: Implement `services/units.py`**

```python
"""SI storage ↔ display units.

Storage: weight kg, distance m, duration s, reps count. The API speaks the
user's display units (Settings: lb/kg, mi/km); durations are seconds on both
sides and formatted by the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

LB_IN_KG = 0.45359237
MI_IN_M = 1609.344
KM_IN_M = 1000.0

STORAGE_COLUMNS = {
    "weight": "weight_kg",
    "reps": "reps",
    "distance": "distance_m",
    "duration": "duration_s",
}


@dataclass(frozen=True)
class UnitPrefs:
    weight_unit: str = "lb"
    distance_unit: str = "mi"


def _distance_factor(prefs: UnitPrefs) -> float:
    return MI_IN_M if prefs.distance_unit == "mi" else KM_IN_M


def to_storage(field: str, value: float | int | None, prefs: UnitPrefs) -> float | int | None:
    STORAGE_COLUMNS[field]  # KeyError for unknown fields
    if value is None:
        return None
    if field == "weight":
        return float(value) * LB_IN_KG if prefs.weight_unit == "lb" else float(value)
    if field == "distance":
        return float(value) * _distance_factor(prefs)
    if field == "reps":
        if float(value) != int(value):
            raise ValueError("reps must be a whole number")
        return int(value)
    return int(round(float(value)))  # duration


def from_storage(field: str, value: float | int | None, prefs: UnitPrefs) -> float | int | None:
    STORAGE_COLUMNS[field]
    if value is None:
        return None
    if field == "weight":
        shown = value / LB_IN_KG if prefs.weight_unit == "lb" else value
        return round(shown, 2)
    if field == "distance":
        return round(value / _distance_factor(prefs), 3)
    return int(value)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_units.py -q`
Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add services/units.py tests/test_units.py
git commit -m "feat: SI storage and display unit conversion"
```

---

### Task 6: Database and schema

**Files:**
- Create: `core/state.py`, `core/migrations/001_initial.sql`
- Test: `tests/test_state.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_state.py`

```python
import sqlite3

import pytest

from core.state import Database

TABLES = {
    "workout", "workout_exercise", "workout_exercise_group", "workout_set",
    "selfcare_session", "selfcare_session_type", "preferences", "schema_migrations",
}


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "t.db"))
    database.migrate()
    yield database
    database.close()


def _workout(conn, ended=None):
    return conn.execute(
        "INSERT INTO workout (started_at, ended_at, local_date, created_at, updated_at) VALUES (?,?,?,?,?)",
        ("2026-09-22T18:00:00+00:00", ended, "2026-09-22", "x", "x"),
    ).lastrowid


def test_migrate_creates_tables_and_is_idempotent(db):
    names = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names
    assert db.migrate() == 1
    assert db.query_one("SELECT COUNT(*) FROM schema_migrations")[0] == 1


def test_only_one_open_workout(db):
    with db.tx() as conn:
        _workout(conn)
        _workout(conn, ended="2026-09-22T19:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        with db.tx() as conn:
            _workout(conn)


def test_tx_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        with db.tx() as conn:
            _workout(conn)
            raise RuntimeError("boom")
    assert db.query_one("SELECT COUNT(*) FROM workout")[0] == 0


def test_foreign_keys_cascade(db):
    with db.tx() as conn:
        wid = _workout(conn)
        we = conn.execute(
            "INSERT INTO workout_exercise (workout_id, position, exercise_key, exercise_name, metric_type, metric_fields) "
            "VALUES (?,1,'bench_press','Bench','weight_reps','weight,reps')",
            (wid,),
        ).lastrowid
        conn.execute("INSERT INTO workout_set (workout_exercise_id, position, updated_at) VALUES (?,1,'x')", (we,))
        conn.execute("DELETE FROM workout WHERE id=?", (wid,))
    assert db.query_one("SELECT COUNT(*) FROM workout_set")[0] == 0


def test_rows_are_mappings(db):
    with db.tx() as conn:
        _workout(conn)
    row = db.query_one("SELECT local_date FROM workout")
    assert row["local_date"] == "2026-09-22"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_state.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'core.state'`

- [ ] **Step 3: Create `core/migrations/001_initial.sql`**

```sql
-- Apollo initial schema. Forward-only: never edit after it has run anywhere;
-- add 002_*.sql instead. Timestamps are UTC ISO-8601; local_date is
-- YYYY-MM-DD from services/clock.py; measurements are SI (kg, m, s).
-- Names are snapshotted at log time so history survives catalog edits.

CREATE TABLE workout (
  id          INTEGER PRIMARY KEY,
  started_at  TEXT NOT NULL,
  ended_at    TEXT,                          -- NULL = open
  local_date  TEXT NOT NULL,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
-- At most one open workout: the indexed expression is 1 for every open row.
CREATE UNIQUE INDEX ux_workout_one_open ON workout(ended_at IS NULL) WHERE ended_at IS NULL;
CREATE INDEX ix_workout_date ON workout(local_date);

CREATE TABLE workout_exercise (
  id            INTEGER PRIMARY KEY,
  workout_id    INTEGER NOT NULL REFERENCES workout(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  exercise_key  TEXT NOT NULL,
  exercise_name TEXT NOT NULL,                -- snapshot
  metric_type   TEXT NOT NULL,                -- snapshot
  metric_fields TEXT NOT NULL,                -- snapshot, e.g. 'weight,reps'
  planned       INTEGER NOT NULL DEFAULT 0,   -- 1 = added by a plan, not the user
  notes         TEXT
);
CREATE INDEX ix_we_workout ON workout_exercise(workout_id);
CREATE INDEX ix_we_key ON workout_exercise(exercise_key);

CREATE TABLE workout_exercise_group (
  workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercise(id) ON DELETE CASCADE,
  muscle_group        TEXT NOT NULL,          -- snapshot
  PRIMARY KEY (workout_exercise_id, muscle_group)
);
CREATE INDEX ix_weg_group ON workout_exercise_group(muscle_group);

CREATE TABLE workout_set (
  id                  INTEGER PRIMARY KEY,
  workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercise(id) ON DELETE CASCADE,
  position            INTEGER NOT NULL,
  done                INTEGER NOT NULL DEFAULT 0,
  weight_kg           REAL,                   -- NULL = not applicable
  reps                INTEGER,
  distance_m          REAL,
  duration_s          INTEGER,
  updated_at          TEXT NOT NULL
);
CREATE INDEX ix_ws_exercise ON workout_set(workout_exercise_id);

CREATE TABLE selfcare_session (
  id           INTEGER PRIMARY KEY,
  category_key TEXT NOT NULL,
  performed_at TEXT NOT NULL,
  local_date   TEXT NOT NULL,
  notes        TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX ix_ss_cat_date ON selfcare_session(category_key, local_date);
CREATE INDEX ix_ss_date ON selfcare_session(local_date);

CREATE TABLE selfcare_session_type (
  session_id INTEGER NOT NULL REFERENCES selfcare_session(id) ON DELETE CASCADE,
  type_key   TEXT NOT NULL,
  type_name  TEXT NOT NULL,                   -- snapshot
  PRIMARY KEY (session_id, type_key)
);
CREATE INDEX ix_sst_type ON selfcare_session_type(type_key);

CREATE TABLE preferences (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

- [ ] **Step 4: Implement `core/state.py`**

```python
"""The one SQLite connection: transactions and forward-only migrations.

stdlib sqlite3 in autocommit mode; writes go through `tx()` (BEGIN IMMEDIATE …
COMMIT/ROLLBACK), reads through `read()`/`query()`. A re-entrant lock
serialises access because FastAPI runs sync handlers on a threadpool.

`tx()` must not be nested — services open one transaction per public method
and pass the connection to their private helpers.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME_RE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA busy_timeout=5000",
        ):
            self._conn.execute(pragma)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            else:
                self._conn.execute("COMMIT")

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def migrate(self, migrations_dir: Path = MIGRATIONS_DIR) -> int:
        """Apply unapplied NNN_name.sql files in order; return the schema version."""
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            applied = {r[0] for r in self._conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(migrations_dir.glob("*.sql")):
                match = _NAME_RE.match(path.name)
                if match is None:
                    raise RuntimeError(f"bad migration filename: {path.name}")
                version, name = int(match.group(1)), match.group(2)
                if version in applied:
                    continue
                now = datetime.now(UTC).isoformat(timespec="seconds")
                script = (
                    "BEGIN;\n"
                    + path.read_text(encoding="utf-8")
                    + f"\nINSERT INTO schema_migrations (version, name, applied_at) "
                    f"VALUES ({version}, '{name}', '{now}');\nCOMMIT;"
                )
                try:
                    self._conn.executescript(script)
                except sqlite3.Error:
                    if self._conn.in_transaction:
                        self._conn.execute("ROLLBACK")
                    raise
            row = self._conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0] or 0)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_state.py -q`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add core/state.py core/migrations/ tests/test_state.py
git commit -m "feat: SQLite database, migrations and initial schema"
```

---

### Task 7: Domain errors and event bus

**Files:**
- Create: `services/errors.py`, `core/events.py`
- Test: `tests/test_events.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_events.py`

```python
from core.events import EventBus
from services.errors import AppError, Conflict, Invalid, NotFound


def test_error_statuses():
    assert (NotFound.status, Conflict.status, Invalid.status) == (404, 409, 422)
    assert issubclass(NotFound, AppError)


def test_publish_reaches_named_and_wildcard_subscribers():
    bus, seen = EventBus(), []
    bus.subscribe("workout.finished", lambda name, payload: seen.append(("named", name, payload)))
    bus.subscribe("*", lambda name, payload: seen.append(("any", name, payload)))
    bus.publish("workout.finished", {"id": 1})
    bus.publish("selfcare.logged", {"id": 2})
    assert seen == [
        ("named", "workout.finished", {"id": 1}),
        ("any", "workout.finished", {"id": 1}),
        ("any", "selfcare.logged", {"id": 2}),
    ]


def test_failing_handler_does_not_stop_others():
    bus, seen = EventBus(), []

    def boom(name, payload):
        raise RuntimeError("handler failed")

    bus.subscribe("x", boom)
    bus.subscribe("x", lambda name, payload: seen.append(payload))
    bus.publish("x", {"ok": True})
    assert seen == [{"ok": True}]
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_events.py -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `services/errors.py`**

```python
"""Domain errors. The API maps each to its HTTP status with the message as `detail`."""


class AppError(Exception):
    status = 400


class NotFound(AppError):
    status = 404


class Conflict(AppError):
    status = 409


class Invalid(AppError):
    status = 422
```

- [ ] **Step 4: Implement `core/events.py`**

```python
"""Minimal in-process event bus.

Services publish facts ("workout.finished", "selfcare.logged") after their
transaction commits. Future features (stats refresh, Claude check-ins,
reminders) subscribe here instead of being called from the loggers.
Subscribe to "*" to receive everything. A failing handler is logged and never
affects the publisher or other handlers.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

Handler = Callable[[str, dict[str, Any]], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, name: str, handler: Handler) -> None:
        self._subscribers[name].append(handler)

    def publish(self, name: str, payload: dict[str, Any]) -> None:
        for handler in [*self._subscribers[name], *self._subscribers["*"]]:
            try:
                handler(name, payload)
            except Exception:
                logger.exception("event handler failed for %s", name)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_events.py -q`
Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add services/errors.py core/events.py tests/test_events.py
git commit -m "feat: domain errors and event bus"
```

---

### Task 8: Preferences

**Files:**
- Create: `services/preferences.py`
- Test: `tests/test_preferences.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_preferences.py`

```python
import pytest

from core.state import Database
from schemas.config import SettingsDefaults
from services import preferences
from services.errors import Invalid
from services.units import UnitPrefs

NOW = "2026-09-22T18:00:00+00:00"


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "t.db"))
    database.migrate()
    yield database
    database.close()


def test_allowed_values_come_from_the_schema():
    assert preferences.ALLOWED["calendar_view"] == ("week", "month", "year")
    assert set(preferences.ALLOWED) == set(SettingsDefaults.model_fields)


def test_seed_only_on_first_run(db):
    preferences.seed(db, SettingsDefaults(calendar_view="week"), NOW)
    preferences.seed(db, SettingsDefaults(calendar_view="year"), NOW)
    assert preferences.get_all(db, SettingsDefaults())["calendar_view"] == "week"


def test_missing_rows_fall_back_to_defaults(db):
    assert preferences.get_all(db, SettingsDefaults(weight_unit="kg"))["weight_unit"] == "kg"


def test_set_validates(db):
    preferences.set_pref(db, "weight_unit", "kg", NOW)
    assert preferences.get_all(db, SettingsDefaults())["weight_unit"] == "kg"
    with pytest.raises(Invalid, match="must be one of"):
        preferences.set_pref(db, "weight_unit", "stone", NOW)
    with pytest.raises(Invalid, match="unknown setting"):
        preferences.set_pref(db, "theme", "dark", NOW)


def test_unit_prefs(db):
    preferences.seed(db, SettingsDefaults(weight_unit="kg", distance_unit="km"), NOW)
    assert preferences.unit_prefs(db, SettingsDefaults()) == UnitPrefs("kg", "km")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_preferences.py -q`
Expected: FAIL — `ImportError: cannot import name 'preferences'`

- [ ] **Step 3: Implement `services/preferences.py`**

```python
"""Settings-tab preferences (the Hermes pattern).

Seeded from apollo.yaml `settings_defaults` on first run; after that the
database is authoritative and YAML edits to these keys are ignored.
Allowed values are read from the SettingsDefaults Literal types, so the YAML
schema and this validator can never disagree.
"""

from __future__ import annotations

from typing import get_args

from core.state import Database
from schemas.config import SettingsDefaults
from services.errors import Invalid
from services.units import UnitPrefs

ALLOWED: dict[str, tuple[str, ...]] = {
    name: get_args(field.annotation) for name, field in SettingsDefaults.model_fields.items()
}


def seed(db: Database, defaults: SettingsDefaults, now_iso: str) -> None:
    with db.tx() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now_iso) for key, value in defaults.model_dump().items()],
        )


def get_all(db: Database, defaults: SettingsDefaults) -> dict[str, str]:
    stored = {r["key"]: r["value"] for r in db.query("SELECT key, value FROM preferences")}
    return {key: stored.get(key, value) for key, value in defaults.model_dump().items()}


def set_pref(db: Database, key: str, value: str, now_iso: str) -> None:
    if key not in ALLOWED:
        raise Invalid(f"unknown setting {key!r}")
    if value not in ALLOWED[key]:
        raise Invalid(f"{key} must be one of: {', '.join(ALLOWED[key])}")
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now_iso),
        )


def unit_prefs(db: Database, defaults: SettingsDefaults) -> UnitPrefs:
    prefs = get_all(db, defaults)
    return UnitPrefs(weight_unit=prefs["weight_unit"], distance_unit=prefs["distance_unit"])
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_preferences.py -q`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add services/preferences.py tests/test_preferences.py
git commit -m "feat: preferences seeded from apollo.yaml"
```

---

### Task 9: Workouts — schemas, fixtures, logging

**Files:**
- Create: `schemas/workouts.py`, `services/workouts.py`, `tests/conftest.py`
- Test: `tests/test_workouts.py`

- [ ] **Step 1: Create the shared fixtures** — `tests/conftest.py`

```python
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
```

- [ ] **Step 2: Write the failing tests** — `tests/test_workouts.py`

```python
import pytest

from services.errors import Conflict, Invalid, NotFound
from services.workouts import WorkoutService


@pytest.fixture
def workouts(env):
    return WorkoutService(env.db, env.catalog, env.clock, env.bus, stale_hours=12)


def log_exercise(workouts, workout_id, key, values):
    """Add `key` and log one done set per dict in `values` (SI units)."""
    ex = workouts.add_exercise(workout_id, key)
    set_ids = [ex.sets[0].id] + [workouts.add_set(workout_id, ex.id).id for _ in values[1:]]
    for set_id, vals in zip(set_ids, values):
        workouts.update_set(set_id, {**vals, "done": True})
    return ex.id


def test_start_creates_open_workout(workouts):
    w = workouts.start([])
    assert w.ended_at is None
    assert w.local_date == "2026-09-22"
    assert w.exercises == [] and w.focus == []
    assert workouts.get_open().id == w.id


def test_no_open_workout(workouts):
    assert workouts.get_open() is None


def test_start_twice_conflicts(workouts):
    workouts.start([])
    with pytest.raises(Conflict, match="already in progress"):
        workouts.start([])


def test_start_with_planned_exercises(workouts):
    w = workouts.start(["bench_press", "run"])
    assert [e.exercise_key for e in w.exercises] == ["bench_press", "run"]
    assert all(e.planned for e in w.exercises)


def test_start_with_unknown_planned_exercise_creates_nothing(workouts):
    with pytest.raises(Invalid, match="unknown exercise 'nope'"):
        workouts.start(["bench_press", "nope"])
    assert workouts.get_open() is None


def test_add_exercise_snapshots_catalog(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "squat")
    assert ex.name == "Back Squat"
    assert ex.metric_type == "weight_reps"
    assert ex.fields == ["weight", "reps"]
    assert ex.muscle_groups == ["legs", "glutes"]
    assert ex.planned is False
    assert [(s.done, s.weight, s.reps) for s in ex.sets] == [(False, None, None)]
    assert workouts.get(w.id).focus == ["legs", "glutes"]


def test_add_unknown_exercise_invalid(workouts):
    w = workouts.start([])
    with pytest.raises(Invalid):
        workouts.add_exercise(w.id, "nope")


def test_prefill_copies_done_sets_from_last_finished_workout(workouts, now):
    w1 = workouts.start([])
    log_exercise(workouts, w1.id, "bench_press", [{"weight": 60.0, "reps": 8}, {"weight": 62.5, "reps": 6}])
    workouts.finish(w1.id)
    now.advance(days=2)
    w2 = workouts.start([])
    ex = workouts.add_exercise(w2.id, "bench_press")
    assert [(s.weight, s.reps, s.done) for s in ex.sets] == [(60.0, 8, False), (62.5, 6, False)]


def test_prefill_ignores_the_open_workout(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "bench_press", [{"weight": 60.0, "reps": 8}])
    again = workouts.add_exercise(w.id, "bench_press")
    assert [(s.weight, s.reps) for s in again.sets] == [(None, None)]


def test_add_set_copies_previous_values(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "bench_press")
    workouts.update_set(ex.sets[0].id, {"weight": 50.0, "reps": 5})
    new = workouts.add_set(w.id, ex.id)
    assert (new.position, new.weight, new.reps, new.done) == (2, 50.0, 5, False)


def test_add_set_to_exercise_of_another_workout_is_not_found(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(NotFound):
        workouts.add_set(w.id + 1, ex.id)


def test_update_set_rejects_fields_outside_metric_type(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(Invalid, match="weight does not apply to Plank"):
        workouts.update_set(ex.sets[0].id, {"weight": 10.0})
    assert workouts.update_set(ex.sets[0].id, {"duration": 60}).duration == 60


def test_update_set_rejects_unknown_keys_and_null_done(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(Invalid):
        workouts.update_set(ex.sets[0].id, {"speed": 3})
    with pytest.raises(Invalid):
        workouts.update_set(ex.sets[0].id, {"done": None})


def test_toggle_done_and_undo(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "pull_up")
    sid = ex.sets[0].id
    assert workouts.update_set(sid, {"reps": 10, "done": True}).done is True
    assert workouts.update_set(sid, {"done": False}).done is False


def test_update_missing_set_not_found(workouts):
    with pytest.raises(NotFound):
        workouts.update_set(999, {"done": True})


def test_delete_set_and_exercise(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "bench_press")
    second = workouts.add_set(w.id, ex.id)
    workouts.delete_set(second.id)
    assert len(workouts.get(w.id).exercises[0].sets) == 1
    workouts.remove_exercise(w.id, ex.id)
    assert workouts.get(w.id).exercises == []


def test_get_missing_workout_not_found(workouts):
    with pytest.raises(NotFound):
        workouts.get(42)
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_workouts.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.workouts'`

- [ ] **Step 4: Implement `schemas/workouts.py`**

```python
"""Workout payloads.

Service methods return these with SI values (weight kg, distance m,
duration s). The API layer converts weight and distance to display units
before responding, so the same models serve both sides.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SetOut(BaseModel):
    id: int
    position: int
    done: bool
    weight: float | None = None
    reps: int | None = None
    distance: float | None = None
    duration: int | None = None


class ExerciseOut(BaseModel):
    id: int
    position: int
    exercise_key: str
    name: str
    metric_type: str
    fields: list[str]
    muscle_groups: list[str]
    planned: bool
    notes: str | None = None
    sets: list[SetOut]


class WorkoutOut(BaseModel):
    id: int
    started_at: str
    ended_at: str | None
    local_date: str
    notes: str | None = None
    focus: list[str]
    exercises: list[ExerciseOut]
    stale: bool = False


class WorkoutSummary(BaseModel):
    id: int
    local_date: str
    started_at: str
    ended_at: str
    duration_s: int
    focus: list[str]
    exercise_count: int
    set_count: int


class FinishOut(BaseModel):
    workout: WorkoutOut | None
    deleted: bool


class StartWorkoutIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    planned_exercises: list[str] = []


class AddExerciseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exercise_key: str


class SetPatch(BaseModel):
    """Partial update. Only fields present in the request are applied;
    an explicit null clears a value. Values are in display units."""

    model_config = ConfigDict(extra="forbid")
    weight: float | None = Field(None, ge=0, le=2000)
    reps: int | None = Field(None, ge=0, le=1000)
    distance: float | None = Field(None, ge=0, le=1000)
    duration: int | None = Field(None, ge=0, le=86_400)
    done: bool | None = None
```

- [ ] **Step 5: Implement `services/workouts.py` (logging half)**

```python
"""Workout lifecycle: start, add exercises (prefilled), log sets, finish.

All values are SI. Rules (spec §5):
- At most one open workout (DB-enforced; surfaced as Conflict).
- A set counts only when done; finishing drops undone sets and empty exercises.
- Prefill copies the done sets of the most recent *finished* workout that
  contained the exercise, as new undone sets.
- Names, metric fields and muscle groups are snapshotted per exercise.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from core.events import EventBus
from core.state import Database
from schemas.workouts import ExerciseOut, SetOut, WorkoutOut
from services.catalog import Catalog
from services.clock import Clock
from services.errors import Conflict, Invalid, NotFound
from services.units import STORAGE_COLUMNS

PATCHABLE = {"weight", "reps", "distance", "duration", "done"}


def _set_out(row: sqlite3.Row) -> SetOut:
    return SetOut(
        id=row["id"],
        position=row["position"],
        done=bool(row["done"]),
        weight=row["weight_kg"],
        reps=row["reps"],
        distance=row["distance_m"],
        duration=row["duration_s"],
    )


def focus_for(conn: sqlite3.Connection, workout_ids: list[int]) -> dict[int, list[str]]:
    """Distinct muscle groups per workout, in order of first appearance."""
    out: dict[int, list[str]] = {wid: [] for wid in workout_ids}
    if not workout_ids:
        return out
    marks = ",".join("?" * len(workout_ids))
    rows = conn.execute(
        f"""SELECT we.workout_id, weg.muscle_group
              FROM workout_exercise we
              JOIN workout_exercise_group weg ON weg.workout_exercise_id = we.id
             WHERE we.workout_id IN ({marks})
             ORDER BY we.workout_id, we.position, weg.rowid""",
        workout_ids,
    ).fetchall()
    for workout_id, group in rows:
        if group not in out[workout_id]:
            out[workout_id].append(group)
    return out


class WorkoutService:
    def __init__(
        self, db: Database, catalog: Catalog, clock: Clock, bus: EventBus, stale_hours: int
    ) -> None:
        self.db = db
        self.catalog = catalog
        self.clock = clock
        self.bus = bus
        self.stale_hours = stale_hours

    # ------------------------------------------------------------------ reads

    def get(self, workout_id: int) -> WorkoutOut:
        with self.db.read() as conn:
            return self._load(conn, workout_id)

    def get_open(self) -> WorkoutOut | None:
        with self.db.read() as conn:
            row = conn.execute("SELECT id FROM workout WHERE ended_at IS NULL").fetchone()
            if row is None:
                return None
            workout = self._load(conn, row["id"])
        age_h = (self.clock.now() - _parse(workout.started_at)).total_seconds() / 3600
        return workout.model_copy(update={"stale": age_h > self.stale_hours})

    # ------------------------------------------------------------------ logging

    def start(self, planned_exercises: list[str]) -> WorkoutOut:
        for key in planned_exercises:
            if self.catalog.exercise(key) is None:
                raise Invalid(f"unknown exercise {key!r}")
        now = self.clock.now_iso()
        try:
            with self.db.tx() as conn:
                if conn.execute("SELECT 1 FROM workout WHERE ended_at IS NULL").fetchone():
                    raise Conflict("a workout is already in progress")
                workout_id = conn.execute(
                    "INSERT INTO workout (started_at, local_date, created_at, updated_at) VALUES (?,?,?,?)",
                    (now, self.clock.today().isoformat(), now, now),
                ).lastrowid
                for key in planned_exercises:
                    self._add_exercise(conn, workout_id, key, planned=True)
                return self._load(conn, workout_id)
        except sqlite3.IntegrityError as exc:
            raise Conflict("a workout is already in progress") from exc

    def add_exercise(self, workout_id: int, exercise_key: str, planned: bool = False) -> ExerciseOut:
        with self.db.tx() as conn:
            self._require_open(conn, workout_id)
            we_id = self._add_exercise(conn, workout_id, exercise_key, planned)
            return self._exercise(conn, we_id)

    def remove_exercise(self, workout_id: int, workout_exercise_id: int) -> None:
        with self.db.tx() as conn:
            self._require_open(conn, workout_id)
            self._require_exercise(conn, workout_id, workout_exercise_id)
            conn.execute("DELETE FROM workout_exercise WHERE id = ?", (workout_exercise_id,))
            self._touch(conn, workout_id)

    def add_set(self, workout_id: int, workout_exercise_id: int) -> SetOut:
        with self.db.tx() as conn:
            self._require_open(conn, workout_id)
            self._require_exercise(conn, workout_id, workout_exercise_id)
            last = conn.execute(
                "SELECT * FROM workout_set WHERE workout_exercise_id = ? ORDER BY position DESC LIMIT 1",
                (workout_exercise_id,),
            ).fetchone()
            position = (last["position"] if last else 0) + 1
            values = (
                (last["weight_kg"], last["reps"], last["distance_m"], last["duration_s"])
                if last
                else (None, None, None, None)
            )
            set_id = self._insert_set(conn, workout_exercise_id, position, *values)
            self._touch(conn, workout_id)
            return _set_out(conn.execute("SELECT * FROM workout_set WHERE id = ?", (set_id,)).fetchone())

    def update_set(self, set_id: int, patch: dict[str, Any]) -> SetOut:
        unknown = set(patch) - PATCHABLE
        if unknown:
            raise Invalid(f"unknown field(s): {', '.join(sorted(unknown))}")
        if "done" in patch and patch["done"] is None:
            raise Invalid("done must be true or false")
        with self.db.tx() as conn:
            row = conn.execute(
                """SELECT s.id, we.metric_fields, we.exercise_name, w.id AS workout_id, w.ended_at
                     FROM workout_set s
                     JOIN workout_exercise we ON we.id = s.workout_exercise_id
                     JOIN workout w ON w.id = we.workout_id
                    WHERE s.id = ?""",
                (set_id,),
            ).fetchone()
            if row is None:
                raise NotFound(f"set {set_id} not found")
            if row["ended_at"] is not None:
                raise Conflict("workout is finished; reopen it to edit")
            allowed = set(row["metric_fields"].split(","))
            bad = [f for f in patch if f != "done" and f not in allowed]
            if bad:
                raise Invalid(f"{', '.join(bad)} does not apply to {row['exercise_name']}")
            now = self.clock.now_iso()
            assignments, params = [], []
            for field, value in patch.items():
                if field == "done":
                    assignments.append("done = ?")
                    params.append(int(bool(value)))
                else:
                    assignments.append(f"{STORAGE_COLUMNS[field]} = ?")
                    params.append(value)
            assignments.append("updated_at = ?")
            params.append(now)
            conn.execute(f"UPDATE workout_set SET {', '.join(assignments)} WHERE id = ?", (*params, set_id))
            self._touch(conn, row["workout_id"], now)
            return _set_out(conn.execute("SELECT * FROM workout_set WHERE id = ?", (set_id,)).fetchone())

    def delete_set(self, set_id: int) -> None:
        with self.db.tx() as conn:
            row = conn.execute(
                """SELECT w.id AS workout_id, w.ended_at FROM workout_set s
                     JOIN workout_exercise we ON we.id = s.workout_exercise_id
                     JOIN workout w ON w.id = we.workout_id WHERE s.id = ?""",
                (set_id,),
            ).fetchone()
            if row is None:
                raise NotFound(f"set {set_id} not found")
            if row["ended_at"] is not None:
                raise Conflict("workout is finished; reopen it to edit")
            conn.execute("DELETE FROM workout_set WHERE id = ?", (set_id,))
            self._touch(conn, row["workout_id"])

    # ------------------------------------------------------------------ helpers

    def _add_exercise(self, conn: sqlite3.Connection, workout_id: int, key: str, planned: bool) -> int:
        exercise = self.catalog.exercise(key)
        if exercise is None:
            raise Invalid(f"unknown exercise {key!r}")
        fields = self.catalog.fields_for(exercise.type)
        position = conn.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM workout_exercise WHERE workout_id = ?",
            (workout_id,),
        ).fetchone()[0]
        we_id = conn.execute(
            """INSERT INTO workout_exercise
                 (workout_id, position, exercise_key, exercise_name, metric_type, metric_fields, planned)
               VALUES (?,?,?,?,?,?,?)""",
            (workout_id, position, exercise.key, exercise.name, exercise.type, ",".join(fields), int(planned)),
        ).lastrowid
        conn.executemany(
            "INSERT INTO workout_exercise_group (workout_exercise_id, muscle_group) VALUES (?, ?)",
            [(we_id, group) for group in exercise.muscle_groups],
        )
        previous = conn.execute(
            """SELECT s.weight_kg, s.reps, s.distance_m, s.duration_s
                 FROM workout_set s
                WHERE s.done = 1 AND s.workout_exercise_id = (
                      SELECT we.id FROM workout_exercise we JOIN workout w ON w.id = we.workout_id
                       WHERE we.exercise_key = ? AND w.ended_at IS NOT NULL
                       ORDER BY w.started_at DESC, we.position DESC LIMIT 1)
                ORDER BY s.position""",
            (key,),
        ).fetchall()
        if previous:
            for i, prev in enumerate(previous, start=1):
                self._insert_set(conn, we_id, i, *tuple(prev))
        else:
            self._insert_set(conn, we_id, 1, None, None, None, None)
        self._touch(conn, workout_id)
        return we_id

    def _insert_set(
        self,
        conn: sqlite3.Connection,
        we_id: int,
        position: int,
        weight_kg: float | None,
        reps: int | None,
        distance_m: float | None,
        duration_s: int | None,
    ) -> int:
        return conn.execute(
            """INSERT INTO workout_set
                 (workout_exercise_id, position, done, weight_kg, reps, distance_m, duration_s, updated_at)
               VALUES (?,?,0,?,?,?,?,?)""",
            (we_id, position, weight_kg, reps, distance_m, duration_s, self.clock.now_iso()),
        ).lastrowid

    def _touch(self, conn: sqlite3.Connection, workout_id: int, now: str | None = None) -> None:
        conn.execute(
            "UPDATE workout SET updated_at = ? WHERE id = ?", (now or self.clock.now_iso(), workout_id)
        )

    def _require_open(self, conn: sqlite3.Connection, workout_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM workout WHERE id = ?", (workout_id,)).fetchone()
        if row is None:
            raise NotFound(f"workout {workout_id} not found")
        if row["ended_at"] is not None:
            raise Conflict("workout is finished; reopen it to edit")
        return row

    def _require_exercise(self, conn: sqlite3.Connection, workout_id: int, we_id: int) -> None:
        if not conn.execute(
            "SELECT 1 FROM workout_exercise WHERE id = ? AND workout_id = ?", (we_id, workout_id)
        ).fetchone():
            raise NotFound(f"exercise {we_id} not found in workout {workout_id}")

    def _exercise(self, conn: sqlite3.Connection, we_id: int) -> ExerciseOut:
        row = conn.execute("SELECT * FROM workout_exercise WHERE id = ?", (we_id,)).fetchone()
        groups = [
            r[0]
            for r in conn.execute(
                "SELECT muscle_group FROM workout_exercise_group WHERE workout_exercise_id = ? ORDER BY rowid",
                (we_id,),
            )
        ]
        sets = [
            _set_out(s)
            for s in conn.execute(
                "SELECT * FROM workout_set WHERE workout_exercise_id = ? ORDER BY position", (we_id,)
            )
        ]
        return ExerciseOut(
            id=row["id"],
            position=row["position"],
            exercise_key=row["exercise_key"],
            name=row["exercise_name"],
            metric_type=row["metric_type"],
            fields=row["metric_fields"].split(","),
            muscle_groups=groups,
            planned=bool(row["planned"]),
            notes=row["notes"],
            sets=sets,
        )

    def _load(self, conn: sqlite3.Connection, workout_id: int) -> WorkoutOut:
        row = conn.execute("SELECT * FROM workout WHERE id = ?", (workout_id,)).fetchone()
        if row is None:
            raise NotFound(f"workout {workout_id} not found")
        exercises = [
            self._exercise(conn, r["id"])
            for r in conn.execute(
                "SELECT id FROM workout_exercise WHERE workout_id = ? ORDER BY position", (workout_id,)
            )
        ]
        focus: list[str] = []
        for ex in exercises:
            for group in ex.muscle_groups:
                if group not in focus:
                    focus.append(group)
        return WorkoutOut(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            local_date=row["local_date"],
            notes=row["notes"],
            focus=focus,
            exercises=exercises,
        )


def _parse(value: str):
    from services.clock import from_iso

    return from_iso(value)
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_workouts.py -q`
Expected: `16 passed, 1 failed`. The one failure is `test_prefill_copies_done_sets_from_last_finished_workout` with `AttributeError: 'WorkoutService' object has no attribute 'finish'` — expected; `finish` arrives in Task 10.

- [ ] **Step 7: Commit**

```bash
git add schemas/workouts.py services/workouts.py tests/conftest.py tests/test_workouts.py
git commit -m "feat: workout logging — start, exercises with prefill, sets"
```

---

### Task 10: Workouts — finish, reopen, delete, history, stale

**Files:**
- Modify: `services/workouts.py` (add methods; replace the `_parse` helper)
- Test: `tests/test_workouts.py` (append)

- [ ] **Step 1: Append the failing tests to `tests/test_workouts.py`**

```python
from datetime import UTC, datetime


def test_finish_drops_undone_sets_and_empty_exercises(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "bench_press", [{"weight": 60.0, "reps": 8}])
    bench = workouts.get(w.id).exercises[0]
    workouts.add_set(w.id, bench.id)              # second set, never ticked
    workouts.add_exercise(w.id, "plank")          # exercise with nothing ticked
    result = workouts.finish(w.id)
    assert result is not None and result.ended_at is not None
    assert [e.exercise_key for e in result.exercises] == ["bench_press"]
    assert len(result.exercises[0].sets) == 1


def test_finish_with_nothing_done_deletes_the_workout(workouts):
    w = workouts.start([])
    workouts.add_exercise(w.id, "plank")
    assert workouts.finish(w.id) is None
    with pytest.raises(NotFound):
        workouts.get(w.id)


def test_finish_publishes_event(env, workouts):
    seen = []
    env.bus.subscribe("workout.finished", lambda name, payload: seen.append(payload))
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    assert seen == [{"id": w.id}]


def test_finish_at_last_activity(workouts, now):
    w = workouts.start([])
    now.advance(minutes=10)
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    now.advance(hours=20)
    result = workouts.finish(w.id, end_at_last_activity=True)
    assert result.ended_at == "2026-09-22T18:10:00+00:00"


def test_finish_twice_conflicts(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    with pytest.raises(Conflict):
        workouts.finish(w.id)


def test_reopen_edit_and_refinish(workouts, now):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    now.advance(days=1)
    reopened = workouts.reopen(w.id)
    assert reopened.ended_at is None and reopened.local_date == "2026-09-22"
    workouts.update_set(reopened.exercises[0].sets[0].id, {"reps": 12})
    again = workouts.finish(w.id)
    assert again.exercises[0].sets[0].reps == 12


def test_reopen_conflicts_when_another_is_open(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    workouts.start([])
    with pytest.raises(Conflict):
        workouts.reopen(w.id)


def test_reopen_open_workout_conflicts(workouts):
    w = workouts.start([])
    with pytest.raises(Conflict):
        workouts.reopen(w.id)


def test_delete_workout(workouts):
    w = workouts.start([])
    workouts.delete(w.id)
    assert workouts.get_open() is None
    with pytest.raises(NotFound):
        workouts.delete(w.id)


def test_focus_first_appearance_order(workouts):
    w = workouts.start([])
    for key in ("bench_press", "barbell_row", "bench_press", "squat"):
        workouts.add_exercise(w.id, key)
    assert workouts.get(w.id).focus == ["chest", "back", "legs", "glutes"]


def test_history_ranges_and_summary(workouts, now):
    def finished_on(dt, key="pull_up"):
        now.dt = dt
        w = workouts.start([])
        log_exercise(workouts, w.id, key, [{"reps": 10}, {"reps": 8}])
        now.advance(minutes=45)
        workouts.finish(w.id)
        return w.id

    old = finished_on(datetime(2026, 8, 13, 18, 0, tzinfo=UTC))    # 40 days before
    mid = finished_on(datetime(2026, 9, 12, 18, 0, tzinfo=UTC))    # 10 days before
    new = finished_on(datetime(2026, 9, 22, 18, 0, tzinfo=UTC), "bench_press")
    workouts.start([])                                             # open — never listed
    assert [s.id for s in workouts.history("1W")] == [new]
    assert [s.id for s in workouts.history("1M")] == [new, mid]
    assert [s.id for s in workouts.history("1Y")] == [new, mid, old]
    summary = workouts.history("1W")[0]
    assert (summary.duration_s, summary.focus, summary.exercise_count, summary.set_count) == (2700, ["chest"], 1, 2)


def test_get_open_flags_stale(workouts, now):
    workouts.start([])
    assert workouts.get_open().stale is False
    now.advance(hours=13)
    assert workouts.get_open().stale is True
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_workouts.py -q`
Expected: FAIL — `AttributeError: 'WorkoutService' object has no attribute 'finish'`

- [ ] **Step 3: Add the lifecycle methods** — in `services/workouts.py`:

(a) Change the imports block to:

```python
from __future__ import annotations

import sqlite3
from typing import Any

from core.events import EventBus
from core.state import Database
from schemas.workouts import ExerciseOut, SetOut, WorkoutOut, WorkoutSummary
from services.catalog import Catalog
from services.clock import Clock, from_iso
from services.errors import Conflict, Invalid, NotFound
from services.units import STORAGE_COLUMNS
```

(b) In `get_open`, replace `_parse(workout.started_at)` with `from_iso(workout.started_at)`.

(c) Delete the module-level `_parse` function at the bottom of the file.

(d) Add this section to `WorkoutService`, directly after `delete_set`:

```python
    # ------------------------------------------------------------------ lifecycle

    def finish(self, workout_id: int, end_at_last_activity: bool = False) -> WorkoutOut | None:
        """End the workout. Returns None if nothing was done and it was deleted."""
        with self.db.tx() as conn:
            row = self._require_open(conn, workout_id)
            ended_at = self.clock.now_iso()
            if end_at_last_activity:
                last = conn.execute(
                    """SELECT MAX(s.updated_at) FROM workout_set s
                         JOIN workout_exercise we ON we.id = s.workout_exercise_id
                        WHERE we.workout_id = ? AND s.done = 1""",
                    (workout_id,),
                ).fetchone()[0]
                ended_at = max(last or row["started_at"], row["started_at"])
            conn.execute(
                """DELETE FROM workout_set WHERE done = 0 AND workout_exercise_id IN
                     (SELECT id FROM workout_exercise WHERE workout_id = ?)""",
                (workout_id,),
            )
            conn.execute(
                """DELETE FROM workout_exercise WHERE workout_id = ? AND NOT EXISTS
                     (SELECT 1 FROM workout_set s WHERE s.workout_exercise_id = workout_exercise.id)""",
                (workout_id,),
            )
            remaining = conn.execute(
                "SELECT COUNT(*) FROM workout_exercise WHERE workout_id = ?", (workout_id,)
            ).fetchone()[0]
            if remaining == 0:
                conn.execute("DELETE FROM workout WHERE id = ?", (workout_id,))
                result = None
            else:
                conn.execute(
                    "UPDATE workout SET ended_at = ?, updated_at = ? WHERE id = ?",
                    (ended_at, self.clock.now_iso(), workout_id),
                )
                result = self._load(conn, workout_id)
        if result is not None:
            self.bus.publish("workout.finished", {"id": workout_id})
        return result

    def reopen(self, workout_id: int) -> WorkoutOut:
        try:
            with self.db.tx() as conn:
                row = conn.execute("SELECT ended_at FROM workout WHERE id = ?", (workout_id,)).fetchone()
                if row is None:
                    raise NotFound(f"workout {workout_id} not found")
                if row["ended_at"] is None:
                    raise Conflict("workout is already open")
                if conn.execute("SELECT 1 FROM workout WHERE ended_at IS NULL").fetchone():
                    raise Conflict("another workout is in progress; finish or discard it first")
                conn.execute(
                    "UPDATE workout SET ended_at = NULL, updated_at = ? WHERE id = ?",
                    (self.clock.now_iso(), workout_id),
                )
                return self._load(conn, workout_id)
        except sqlite3.IntegrityError as exc:
            raise Conflict("another workout is in progress; finish or discard it first") from exc

    def delete(self, workout_id: int) -> None:
        with self.db.tx() as conn:
            if conn.execute("DELETE FROM workout WHERE id = ?", (workout_id,)).rowcount == 0:
                raise NotFound(f"workout {workout_id} not found")

    def history(self, range_key: str) -> list[WorkoutSummary]:
        since = self.clock.range_start(range_key).isoformat()
        with self.db.read() as conn:
            rows = conn.execute(
                """SELECT w.id, w.local_date, w.started_at, w.ended_at,
                          (SELECT COUNT(*) FROM workout_exercise we WHERE we.workout_id = w.id) AS exercise_count,
                          (SELECT COUNT(*) FROM workout_set s JOIN workout_exercise we
                             ON we.id = s.workout_exercise_id WHERE we.workout_id = w.id) AS set_count
                     FROM workout w
                    WHERE w.ended_at IS NOT NULL AND w.local_date >= ?
                    ORDER BY w.started_at DESC""",
                (since,),
            ).fetchall()
            focus = focus_for(conn, [r["id"] for r in rows])
        return [
            WorkoutSummary(
                id=r["id"],
                local_date=r["local_date"],
                started_at=r["started_at"],
                ended_at=r["ended_at"],
                duration_s=int((from_iso(r["ended_at"]) - from_iso(r["started_at"])).total_seconds()),
                focus=focus[r["id"]],
                exercise_count=r["exercise_count"],
                set_count=r["set_count"],
            )
            for r in rows
        ]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_workouts.py -q`
Expected: `29 passed`

- [ ] **Step 5: Commit**

```bash
git add services/workouts.py tests/test_workouts.py
git commit -m "feat: finish, reopen, delete and history for workouts"
```

---

### Task 11: Self-care

**Files:**
- Create: `schemas/selfcare.py`, `services/selfcare.py`
- Test: `tests/test_selfcare.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_selfcare.py`

```python
from datetime import UTC, date, datetime

import pytest

from services.errors import Invalid, NotFound
from services.selfcare import SelfcareService, compute_due

TODAY = date(2026, 9, 22)


@pytest.fixture
def selfcare(env):
    return SelfcareService(env.db, env.catalog, env.clock, env.bus)


# -------------------------------------------------------------- compute_due


def test_due_untracked_and_never():
    assert compute_due(None, date(2026, 9, 20), TODAY)["status"] == "untracked"
    assert compute_due(None, date(2026, 9, 20), TODAY)["days_since"] == 2
    assert compute_due(7, None, TODAY) == {
        "status": "never", "next_due": None, "days_since": None, "days_over": None, "ratio": None,
    }


@pytest.mark.parametrize(
    ("every", "last", "status", "days_over"),
    [
        (7, date(2026, 9, 21), "ok", -6),       # ratio 1/7
        (7, date(2026, 9, 16), "soon", -1),     # ratio 6/7 ≥ 0.8
        (7, date(2026, 9, 15), "due", 0),       # next_due == today
        (7, date(2026, 9, 11), "overdue", 4),
        (1, date(2026, 9, 22), "ok", -1),       # done today
        (1, date(2026, 9, 21), "due", 0),
    ],
)
def test_due_statuses(every, last, status, days_over):
    result = compute_due(every, last, TODAY)
    assert result["status"] == status
    assert result["days_over"] == days_over


# -------------------------------------------------------------- sessions


def test_log_defaults_to_today(selfcare):
    s = selfcare.log("skincare", ["am_routine", "face_mask"])
    assert s.local_date == "2026-09-22"
    assert s.performed_at == "2026-09-22T18:00:00+00:00"
    assert s.category_name == "Skincare (Face)"
    assert [(t.key, t.name) for t in s.types] == [("am_routine", "AM routine"), ("face_mask", "Face mask")]


def test_log_backdated_is_noon_local(selfcare):
    s = selfcare.log("skincare", ["exfoliation"], on=date(2026, 9, 20), notes="gentle")
    assert s.local_date == "2026-09-20"
    assert s.performed_at == "2026-09-20T19:00:00+00:00"
    assert s.notes == "gentle"


def test_log_validation(selfcare):
    with pytest.raises(Invalid, match="future"):
        selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 23))
    with pytest.raises(Invalid, match="unknown category"):
        selfcare.log("hair", ["am_routine"])
    with pytest.raises(Invalid, match="unknown type 'nope'"):
        selfcare.log("skincare", ["nope"])
    with pytest.raises(Invalid, match="at least one type"):
        selfcare.log("skincare", [])


def test_duplicate_types_are_collapsed(selfcare):
    s = selfcare.log("skincare", ["am_routine", "am_routine"])
    assert [t.key for t in s.types] == ["am_routine"]


def test_log_publishes_event(env, selfcare):
    seen = []
    env.bus.subscribe("selfcare.logged", lambda name, payload: seen.append(payload))
    s = selfcare.log("skincare", ["am_routine"])
    assert seen == [{"id": s.id, "category": "skincare", "types": ["am_routine"]}]


def test_update_and_delete(selfcare):
    s = selfcare.log("skincare", ["am_routine"])
    updated = selfcare.update(s.id, {"types": ["exfoliation"], "date": date(2026, 9, 21), "notes": "x"})
    assert [t.key for t in updated.types] == ["exfoliation"]
    assert (updated.local_date, updated.notes) == ("2026-09-21", "x")
    selfcare.delete(s.id)
    with pytest.raises(NotFound):
        selfcare.get(s.id)
    with pytest.raises(NotFound):
        selfcare.delete(s.id)


def test_history_range(selfcare):
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 22))
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 1))
    selfcare.log("skincare", ["am_routine"], on=date(2026, 3, 1))
    assert [s.local_date for s in selfcare.history("1W")] == ["2026-09-22"]
    assert [s.local_date for s in selfcare.history("1M")] == ["2026-09-22", "2026-09-01"]
    assert len(selfcare.history("1Y")) == 3
    assert selfcare.history("1Y", category="other") == []


def test_due_list_order_and_untracked_last(selfcare):
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 21))     # due today
    selfcare.log("skincare", ["face_mask"], on=date(2026, 9, 20))      # untracked
    items = selfcare.due_list()
    assert [(i.type_key, i.status) for i in items] == [
        ("exfoliation", "never"),
        ("am_routine", "due"),
        ("face_mask", "untracked"),
    ]
    assert items[1].last_done == "2026-09-21" and items[1].next_due == "2026-09-22"
    assert items[2].days_since == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_selfcare.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.selfcare'`

- [ ] **Step 3: Implement `schemas/selfcare.py`**

```python
from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# `datetime as dt`: two models have a field named `date`, which would shadow a
# bare `date` type in their own annotations.


class TypeRef(BaseModel):
    key: str
    name: str


class SelfcareSessionOut(BaseModel):
    id: int
    category_key: str
    category_name: str
    local_date: str
    performed_at: str
    notes: str | None = None
    types: list[TypeRef]


class LogSelfcareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: str
    types: list[str] = Field(min_length=1)
    date: dt.date | None = None
    notes: str | None = Field(None, max_length=2000)


class UpdateSelfcareIn(BaseModel):
    """Partial update; only fields present in the request are applied."""

    model_config = ConfigDict(extra="forbid")
    types: list[str] | None = Field(None, min_length=1)
    date: dt.date | None = None
    notes: str | None = Field(None, max_length=2000)


DueStatus = Literal["never", "ok", "soon", "due", "overdue", "untracked"]


class DueItem(BaseModel):
    category_key: str
    type_key: str
    type_name: str
    every_days: int | None
    last_done: str | None
    next_due: str | None
    days_since: int | None
    days_over: int | None
    ratio: float | None
    status: DueStatus
```

- [ ] **Step 4: Implement `services/selfcare.py`**

```python
"""Self-care sessions and the due list.

A session is a date plus one or more configured types of one category.
Due logic (spec §5) is computed on read from the sessions, never stored:
next_due = last_done + every_days; ratio = days_since / every_days.
"""

from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta
from typing import Any

from core.events import EventBus
from core.state import Database
from schemas.config import SelfcareCategory
from schemas.selfcare import DueItem, SelfcareSessionOut, TypeRef
from services.catalog import Catalog
from services.clock import Clock, to_iso
from services.errors import Invalid, NotFound

SOON_RATIO = 0.8


def compute_due(every_days: int | None, last_done: date | None, today: date) -> dict[str, Any]:
    days_since = (today - last_done).days if last_done else None
    if every_days is None:
        return {"status": "untracked", "next_due": None, "days_since": days_since, "days_over": None, "ratio": None}
    if last_done is None:
        return {"status": "never", "next_due": None, "days_since": None, "days_over": None, "ratio": None}
    next_due = last_done + timedelta(days=every_days)
    days_over = (today - next_due).days
    ratio = days_since / every_days
    if days_over > 0:
        status = "overdue"
    elif days_over == 0:
        status = "due"
    elif ratio >= SOON_RATIO:
        status = "soon"
    else:
        status = "ok"
    return {"status": status, "next_due": next_due, "days_since": days_since, "days_over": days_over, "ratio": ratio}


class SelfcareService:
    def __init__(self, db: Database, catalog: Catalog, clock: Clock, bus: EventBus) -> None:
        self.db = db
        self.catalog = catalog
        self.clock = clock
        self.bus = bus

    # ------------------------------------------------------------------ writes

    def log(
        self, category: str, types: list[str], on: date | None = None, notes: str | None = None
    ) -> SelfcareSessionOut:
        cat = self._category(category)
        keys = self._check_types(cat, types)
        local_date, performed_at = self._when(on)
        now = self.clock.now_iso()
        with self.db.tx() as conn:
            session_id = conn.execute(
                """INSERT INTO selfcare_session
                     (category_key, performed_at, local_date, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (cat.key, performed_at, local_date.isoformat(), notes, now, now),
            ).lastrowid
            self._insert_types(conn, session_id, cat, keys)
        self.bus.publish("selfcare.logged", {"id": session_id, "category": cat.key, "types": keys})
        return self.get(session_id)

    def update(self, session_id: int, changes: dict[str, Any]) -> SelfcareSessionOut:
        with self.db.tx() as conn:
            row = conn.execute("SELECT * FROM selfcare_session WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise NotFound(f"session {session_id} not found")
            cat = self._category(row["category_key"])
            if "types" in changes:
                keys = self._check_types(cat, changes["types"] or [])
                conn.execute("DELETE FROM selfcare_session_type WHERE session_id = ?", (session_id,))
                self._insert_types(conn, session_id, cat, keys)
            if "date" in changes:
                local_date, performed_at = self._when(changes["date"])
                conn.execute(
                    "UPDATE selfcare_session SET local_date = ?, performed_at = ? WHERE id = ?",
                    (local_date.isoformat(), performed_at, session_id),
                )
            if "notes" in changes:
                conn.execute("UPDATE selfcare_session SET notes = ? WHERE id = ?", (changes["notes"], session_id))
            conn.execute(
                "UPDATE selfcare_session SET updated_at = ? WHERE id = ?", (self.clock.now_iso(), session_id)
            )
        return self.get(session_id)

    def delete(self, session_id: int) -> None:
        with self.db.tx() as conn:
            if conn.execute("DELETE FROM selfcare_session WHERE id = ?", (session_id,)).rowcount == 0:
                raise NotFound(f"session {session_id} not found")

    # ------------------------------------------------------------------ reads

    def get(self, session_id: int) -> SelfcareSessionOut:
        with self.db.read() as conn:
            row = conn.execute("SELECT * FROM selfcare_session WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                raise NotFound(f"session {session_id} not found")
            return self._session_out(conn, row)

    def history(self, range_key: str, category: str | None = None) -> list[SelfcareSessionOut]:
        since = self.clock.range_start(range_key).isoformat()
        sql = "SELECT * FROM selfcare_session WHERE local_date >= ?"
        params: list[Any] = [since]
        if category is not None:
            sql += " AND category_key = ?"
            params.append(category)
        sql += " ORDER BY local_date DESC, performed_at DESC"
        with self.db.read() as conn:
            return [self._session_out(conn, r) for r in conn.execute(sql, params).fetchall()]

    def due_list(self) -> list[DueItem]:
        today = self.clock.today()
        with self.db.read() as conn:
            last = {
                (r[0], r[1]): date.fromisoformat(r[2])
                for r in conn.execute(
                    """SELECT s.category_key, t.type_key, MAX(s.local_date)
                         FROM selfcare_session s JOIN selfcare_session_type t ON t.session_id = s.id
                        GROUP BY s.category_key, t.type_key"""
                )
            }
        items = []
        for cat in self.catalog.selfcare.categories:
            for t in cat.types:
                due = compute_due(t.every_days, last.get((cat.key, t.key)), today)
                items.append(
                    DueItem(
                        category_key=cat.key,
                        type_key=t.key,
                        type_name=t.name,
                        every_days=t.every_days,
                        last_done=last[(cat.key, t.key)].isoformat() if (cat.key, t.key) in last else None,
                        next_due=due["next_due"].isoformat() if due["next_due"] else None,
                        days_since=due["days_since"],
                        days_over=due["days_over"],
                        ratio=due["ratio"],
                        status=due["status"],
                    )
                )
        tracked = [i for i in items if i.status != "untracked"]
        untracked = [i for i in items if i.status == "untracked"]
        tracked.sort(key=lambda i: -(math.inf if i.ratio is None else i.ratio))
        return tracked + untracked

    # ------------------------------------------------------------------ helpers

    def _category(self, key: str) -> SelfcareCategory:
        cat = self.catalog.category(key)
        if cat is None:
            raise Invalid(f"unknown category {key!r}")
        return cat

    def _check_types(self, cat: SelfcareCategory, types: list[str]) -> list[str]:
        keys = list(dict.fromkeys(types))
        if not keys:
            raise Invalid("choose at least one type")
        known = {t.key for t in cat.types}
        for key in keys:
            if key not in known:
                raise Invalid(f"unknown type {key!r} for {cat.name}")
        return keys

    def _when(self, on: date | None) -> tuple[date, str]:
        today = self.clock.today()
        if on is None or on == today:
            return today, self.clock.now_iso()
        if on > today:
            raise Invalid("date cannot be in the future")
        return on, to_iso(self.clock.local_noon_utc(on))

    def _insert_types(self, conn: sqlite3.Connection, session_id: int, cat: SelfcareCategory, keys: list[str]) -> None:
        names = {t.key: t.name for t in cat.types}
        conn.executemany(
            "INSERT INTO selfcare_session_type (session_id, type_key, type_name) VALUES (?,?,?)",
            [(session_id, key, names[key]) for key in keys],
        )

    def _session_out(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SelfcareSessionOut:
        types = [
            TypeRef(key=r["type_key"], name=r["type_name"])
            for r in conn.execute(
                "SELECT type_key, type_name FROM selfcare_session_type WHERE session_id = ? ORDER BY rowid",
                (row["id"],),
            )
        ]
        cat = self.catalog.category(row["category_key"])
        return SelfcareSessionOut(
            id=row["id"],
            category_key=row["category_key"],
            category_name=cat.name if cat else row["category_key"],
            local_date=row["local_date"],
            performed_at=row["performed_at"],
            notes=row["notes"],
            types=types,
        )
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_selfcare.py -q`
Expected: `15 passed`

- [ ] **Step 6: Commit**

```bash
git add schemas/selfcare.py services/selfcare.py tests/test_selfcare.py
git commit -m "feat: self-care sessions and due list"
```

---

### Task 12: Calendar

**Files:**
- Create: `schemas/calendar.py`, `services/calendar.py`
- Test: `tests/test_calendar.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_calendar.py`

```python
from datetime import UTC, date, datetime

import pytest

from services.calendar import CalendarService
from services.errors import Invalid
from services.selfcare import SelfcareService
from services.workouts import WorkoutService


@pytest.fixture
def svc(env):
    workouts = WorkoutService(env.db, env.catalog, env.clock, env.bus, stale_hours=12)
    selfcare = SelfcareService(env.db, env.catalog, env.clock, env.bus)
    return workouts, selfcare, CalendarService(env.db, env.catalog)


def finished(workouts, now, dt, keys):
    now.dt = dt
    w = workouts.start([])
    for key in keys:
        ex = workouts.add_exercise(w.id, key)
        field = "reps" if key == "pull_up" else "weight"
        workouts.update_set(ex.sets[0].id, {field: 10, "done": True})
    now.advance(minutes=52)
    workouts.finish(w.id)
    return w.id


def test_entries_merge_kinds_and_sort_by_time(svc, now):
    workouts, selfcare, calendar = svc
    wid = finished(workouts, now, datetime(2026, 9, 21, 17, 0, tzinfo=UTC), ["bench_press", "barbell_row"])
    now.dt = datetime(2026, 9, 22, 18, 0, tzinfo=UTC)
    sid = selfcare.log("skincare", ["am_routine", "exfoliation"], on=date(2026, 9, 21))  # noon local = 19:00Z
    days = calendar.entries(date(2026, 9, 20), date(2026, 9, 22), {"workout", "selfcare"})
    assert [d.date for d in days] == ["2026-09-21"]
    entries = days[0].entries
    assert [(e.kind, e.id) for e in entries] == [("workout", wid), ("selfcare", sid)]
    assert entries[0].title == "Chest · Back"
    assert entries[0].summary == "2 exercises · 52 min"
    assert entries[1].title == "Skincare (Face)"
    assert entries[1].summary == "AM routine, Exfoliation"


def test_kind_filter(svc, now):
    workouts, selfcare, calendar = svc
    finished(workouts, now, datetime(2026, 9, 22, 17, 0, tzinfo=UTC), ["pull_up"])
    selfcare.log("skincare", ["am_routine"])
    days = calendar.entries(date(2026, 9, 22), date(2026, 9, 22), {"selfcare"})
    assert [e.kind for e in days[0].entries] == ["selfcare"]


def test_in_progress_workout_listed(svc):
    workouts, _, calendar = svc
    w = workouts.start([])
    workouts.add_exercise(w.id, "plank")
    entry = calendar.entries(date(2026, 9, 22), date(2026, 9, 22), {"workout"})[0].entries[0]
    assert entry.in_progress is True
    assert entry.summary == "1 exercise · in progress"


def test_multiple_sessions_per_day(svc):
    _, selfcare, calendar = svc
    selfcare.log("skincare", ["am_routine"])
    selfcare.log("skincare", ["face_mask"])
    assert len(calendar.entries(date(2026, 9, 22), date(2026, 9, 22), {"selfcare"})[0].entries) == 2


def test_range_validation(svc):
    _, _, calendar = svc
    with pytest.raises(Invalid):
        calendar.entries(date(2026, 9, 22), date(2026, 9, 1), {"workout"})
    with pytest.raises(Invalid):
        calendar.entries(date(2024, 1, 1), date(2026, 1, 1), {"workout"})
    with pytest.raises(Invalid):
        calendar.entries(date(2026, 9, 1), date(2026, 9, 2), {"sleep"})


def test_last_done(svc, now):
    workouts, selfcare, calendar = svc
    assert calendar.last_done().model_dump() == {"workout": None, "selfcare": None, "types": {}}
    finished(workouts, now, datetime(2026, 9, 20, 17, 0, tzinfo=UTC), ["pull_up"])
    now.dt = datetime(2026, 9, 22, 18, 0, tzinfo=UTC)
    workouts.start([])                                   # open: not "done"
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 21))
    last = calendar.last_done()
    assert (last.workout, last.selfcare) == ("2026-09-20", "2026-09-21")
    assert last.types == {"skincare.am_routine": "2026-09-21"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_calendar.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'services.calendar'`

- [ ] **Step 3: Implement `schemas/calendar.py`**

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Kind = Literal["workout", "selfcare"]


class CalendarEntry(BaseModel):
    kind: Kind
    id: int
    title: str
    summary: str
    in_progress: bool = False


class CalendarDay(BaseModel):
    date: str
    entries: list[CalendarEntry]


class LastDone(BaseModel):
    workout: str | None
    selfcare: str | None
    types: dict[str, str]   # "category.type" -> YYYY-MM-DD
```

- [ ] **Step 4: Implement `services/calendar.py`**

```python
"""Per-day summaries across both kinds, and "when did I last…".

Summaries only — a day never carries full sets. The UI opens details by id.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from core.state import Database
from schemas.calendar import CalendarDay, CalendarEntry, LastDone
from services.catalog import Catalog
from services.clock import from_iso
from services.errors import Invalid
from services.workouts import focus_for

KINDS = {"workout", "selfcare"}
MAX_SPAN_DAYS = 400


def _plural(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


class CalendarService:
    def __init__(self, db: Database, catalog: Catalog) -> None:
        self.db = db
        self.catalog = catalog

    def entries(self, start: date, end: date, kinds: set[str]) -> list[CalendarDay]:
        if end < start:
            raise Invalid("'to' must not be before 'from'")
        if (end - start).days > MAX_SPAN_DAYS:
            raise Invalid(f"range too long (max {MAX_SPAN_DAYS} days)")
        unknown = kinds - KINDS
        if unknown or not kinds:
            raise Invalid(f"kinds must be a non-empty subset of: {', '.join(sorted(KINDS))}")
        by_day: dict[str, list[tuple[str, CalendarEntry]]] = defaultdict(list)
        span = (start.isoformat(), end.isoformat())
        with self.db.read() as conn:
            if "workout" in kinds:
                rows = conn.execute(
                    """SELECT w.id, w.local_date, w.started_at, w.ended_at,
                              (SELECT COUNT(*) FROM workout_exercise we WHERE we.workout_id = w.id) AS n
                         FROM workout w WHERE w.local_date BETWEEN ? AND ?""",
                    span,
                ).fetchall()
                focus = focus_for(conn, [r["id"] for r in rows])
                for r in rows:
                    title = " · ".join(g.title() for g in focus[r["id"]]) or "Workout"
                    if r["ended_at"]:
                        minutes = round((from_iso(r["ended_at"]) - from_iso(r["started_at"])).total_seconds() / 60)
                        summary = f"{_plural(r['n'], 'exercise')} · {minutes} min"
                    else:
                        summary = f"{_plural(r['n'], 'exercise')} · in progress"
                    by_day[r["local_date"]].append(
                        (
                            r["started_at"],
                            CalendarEntry(
                                kind="workout", id=r["id"], title=title, summary=summary,
                                in_progress=r["ended_at"] is None,
                            ),
                        )
                    )
            if "selfcare" in kinds:
                rows = conn.execute(
                    "SELECT id, category_key, local_date, performed_at FROM selfcare_session "
                    "WHERE local_date BETWEEN ? AND ?",
                    span,
                ).fetchall()
                names: dict[int, list[str]] = defaultdict(list)
                if rows:
                    marks = ",".join("?" * len(rows))
                    for sid, name in conn.execute(
                        f"SELECT session_id, type_name FROM selfcare_session_type "
                        f"WHERE session_id IN ({marks}) ORDER BY rowid",
                        [r["id"] for r in rows],
                    ):
                        names[sid].append(name)
                for r in rows:
                    cat = self.catalog.category(r["category_key"])
                    by_day[r["local_date"]].append(
                        (
                            r["performed_at"],
                            CalendarEntry(
                                kind="selfcare", id=r["id"],
                                title=cat.name if cat else r["category_key"],
                                summary=", ".join(names[r["id"]]),
                            ),
                        )
                    )
        return [
            CalendarDay(date=day, entries=[entry for _, entry in sorted(items, key=lambda x: x[0])])
            for day, items in sorted(by_day.items())
        ]

    def last_done(self) -> LastDone:
        with self.db.read() as conn:
            workout = conn.execute("SELECT MAX(local_date) FROM workout WHERE ended_at IS NOT NULL").fetchone()[0]
            selfcare = conn.execute("SELECT MAX(local_date) FROM selfcare_session").fetchone()[0]
            types = {
                f"{r[0]}.{r[1]}": r[2]
                for r in conn.execute(
                    """SELECT s.category_key, t.type_key, MAX(s.local_date)
                         FROM selfcare_session s JOIN selfcare_session_type t ON t.session_id = s.id
                        GROUP BY s.category_key, t.type_key"""
                )
            }
        return LastDone(workout=workout, selfcare=selfcare, types=types)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_calendar.py -q`
Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add schemas/calendar.py services/calendar.py tests/test_calendar.py
git commit -m "feat: calendar summaries and last-done"
```

---

### Task 13: Container, metrics placeholder, app wiring

**Files:**
- Create: `core/container.py`, `services/metrics.py`
- Modify: `main.py` (replace), `core/api.py` (replace — health moves under `/api` in Task 14; for now keep `/health` working), `Makefile` (`run-dev`)
- Test: `tests/test_health.py` (replace)

- [ ] **Step 1: Write the failing test** — replace `tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from config import Settings
from main import build_app


def test_build_app_boots_on_a_fresh_db(tmp_path, config_dir, now):
    settings = Settings(DB_PATH=str(tmp_path / "t.db"), CONFIG_DIR=str(config_dir), WEB_DIR=str(tmp_path / "none"))
    with TestClient(build_app(settings, now_fn=now)) as client:
        assert client.get("/api/health").json()["status"] == "ok"


def test_importing_main_does_not_create_a_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import importlib

    import main

    importlib.reload(main)
    assert not (tmp_path / "apollo.db").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_health.py -q`
Expected: FAIL — `TypeError: build_app() got an unexpected keyword argument 'now_fn'`

- [ ] **Step 3: Create `core/container.py`**

```python
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
```

- [ ] **Step 4: Create `services/metrics.py`**

```python
"""Stats over logged data — not built in the MVP.

This is where derived numbers will live, as pure functions over stored sets
(SI units, done sets only), computed on read and never persisted:

- estimated 1RM per set (formula configurable; Brzycki default, Epley
  alternative; eligible sets: weight > 0, 1 ≤ reps ≤ 10, not warmups)
- personal records per exercise: heaviest weight, best e1RM, most reps,
  longest duration, longest distance, best pace
- volume per session / week / muscle group
- distance totals per exercise per period
- self-care frequency per type per period

Query shapes are listed in docs/2026-09-22-mvp-spec.md §4.
"""
```

- [ ] **Step 5: Replace `main.py`**

```python
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
```

- [ ] **Step 6: Replace `core/api.py` with the skeleton (routes added in Task 14)**

```python
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
```

- [ ] **Step 7: Update the Makefile `run-dev` target** — replace its recipe line with:

```make
	$(UV) run uvicorn main:build_app --factory --reload --host $(HOST) --port $(PORT)
```

- [ ] **Step 8: Run all tests**

Run: `uv run pytest -q`
Expected: all pass (`test_health.py` 2 passed).

- [ ] **Step 9: Commit**

```bash
git add core/container.py services/metrics.py main.py core/api.py Makefile tests/test_health.py
git commit -m "feat: wire services into the app; health under /api"
```

---

### Task 14: API routes

**Files:**
- Modify: `core/api.py` (add routers and the unit-conversion helpers)
- Modify: `tests/conftest.py` (add `client` fixture)
- Test: `tests/test_api.py`

- [ ] **Step 1: Add the `client` fixture** — append to `tests/conftest.py`:

```python
@pytest.fixture
def client(tmp_path: Path, config_dir: Path, now: FakeNow):
    from fastapi.testclient import TestClient

    from config import Settings
    from main import build_app

    settings = Settings(
        DB_PATH=str(tmp_path / "api.db"),
        CONFIG_DIR=str(config_dir),
        WEB_DIR=str(tmp_path / "no-ui"),
    )
    with TestClient(build_app(settings, now_fn=now)) as c:
        yield c
```

- [ ] **Step 2: Write the failing tests** — `tests/test_api.py`

```python
import pytest


def start(client, planned=None):
    r = client.post("/api/workouts", json={"planned_exercises": planned or []})
    assert r.status_code == 201, r.text
    return r.json()


def test_health_and_today(client):
    assert client.get("/api/health").json() == {"status": "ok", "config_errors": []}
    assert client.get("/api/today").json() == {"today": "2026-09-22"}


def test_catalog_shape(client):
    c = client.get("/api/catalog").json()
    assert c["metric_types"]["distance_time"] == ["distance", "duration"]
    assert c["muscle_groups"][0] == "chest"
    assert c["exercises_by_group"]["glutes"] == [
        {"key": "squat", "name": "Back Squat", "type": "weight_reps", "groups": ["legs", "glutes"]}
    ]
    assert c["selfcare"][0]["types"][0] == {"key": "am_routine", "name": "AM routine", "every_days": 1}
    assert c["colors"] == {"workout": "#4ade80", "selfcare": "#60a5fa"}


def test_settings_get_and_put(client):
    assert client.get("/api/settings").json()["weight_unit"] == "lb"
    assert client.put("/api/settings/weight_unit", json={"value": "kg"}).status_code == 204
    assert client.get("/api/settings").json()["weight_unit"] == "kg"
    r = client.put("/api/settings/weight_unit", json={"value": "stone"})
    assert r.status_code == 422 and "must be one of" in r.json()["detail"]


def test_workout_flow_with_unit_conversion(client):
    w = start(client, ["bench_press"])
    assert client.post("/api/workouts", json={}).status_code == 409
    ex = w["exercises"][0]
    set_id = ex["sets"][0]["id"]
    r = client.patch(f"/api/sets/{set_id}", json={"weight": 135, "reps": 8, "done": True})
    assert r.status_code == 200
    assert r.json() | {"id": 0} == {"id": 0, "position": 1, "done": True, "weight": 135.0, "reps": 8,
                                    "distance": None, "duration": None}
    client.put("/api/settings/weight_unit", json={"value": "kg"})
    open_w = client.get("/api/workouts/open").json()
    assert open_w["exercises"][0]["sets"][0]["weight"] == pytest.approx(61.23, abs=0.01)
    client.put("/api/settings/weight_unit", json={"value": "lb"})
    fin = client.post(f"/api/workouts/{w['id']}/finish").json()
    assert fin["deleted"] is False and fin["workout"]["ended_at"] is not None
    assert client.get("/api/workouts/open").json() is None
    history = client.get("/api/workouts?range=1W").json()
    assert [h["id"] for h in history] == [w["id"]] and history[0]["focus"] == ["chest"]


def test_workout_errors(client):
    w = start(client)
    r = client.post(f"/api/workouts/{w['id']}/exercises", json={"exercise_key": "plank"})
    assert r.status_code == 201
    set_id = r.json()["sets"][0]["id"]
    assert client.patch(f"/api/sets/{set_id}", json={"weight": 10}).status_code == 422
    assert client.patch(f"/api/sets/{set_id}", json={"reps": -1}).status_code == 422
    assert client.get("/api/workouts/999").status_code == 404
    assert client.get("/api/workouts?range=2W").status_code == 422
    # unknown planned exercises are rejected before the one-open check
    assert client.post("/api/workouts", json={"planned_exercises": ["nope"]}).status_code == 422
    assert client.post("/api/workouts", json={}).status_code == 409


def test_sets_add_delete_and_exercise_delete(client):
    w = start(client)
    ex = client.post(f"/api/workouts/{w['id']}/exercises", json={"exercise_key": "run"}).json()
    s2 = client.post(f"/api/workouts/{w['id']}/exercises/{ex['id']}/sets").json()
    client.patch(f"/api/sets/{s2['id']}", json={"distance": 3.1, "duration": 1800})
    got = client.get(f"/api/workouts/{w['id']}").json()["exercises"][0]["sets"][1]
    assert (got["distance"], got["duration"]) == (3.1, 1800)
    assert client.delete(f"/api/sets/{s2['id']}").status_code == 204
    assert client.delete(f"/api/workouts/{w['id']}/exercises/{ex['id']}").status_code == 204
    assert client.get(f"/api/workouts/{w['id']}").json()["exercises"] == []


def test_finish_empty_reopen_and_delete(client):
    w = start(client, ["plank"])
    assert client.post(f"/api/workouts/{w['id']}/finish").json() == {"workout": None, "deleted": True}
    w = start(client, ["pull_up"])
    sid = w["exercises"][0]["sets"][0]["id"]
    client.patch(f"/api/sets/{sid}", json={"reps": 10, "done": True})
    client.post(f"/api/workouts/{w['id']}/finish")
    assert client.patch(f"/api/sets/{sid}", json={"reps": 11}).status_code == 409
    assert client.post(f"/api/workouts/{w['id']}/reopen").json()["ended_at"] is None
    assert client.delete(f"/api/workouts/{w['id']}").status_code == 204


def test_selfcare_flow(client):
    r = client.post("/api/selfcare/sessions", json={"category": "skincare", "types": ["am_routine"], "date": "2026-09-21"})
    assert r.status_code == 201
    sid = r.json()["id"]
    assert client.get(f"/api/selfcare/sessions/{sid}").json()["local_date"] == "2026-09-21"
    p = client.patch(f"/api/selfcare/sessions/{sid}", json={"notes": "ok"})
    assert p.json()["notes"] == "ok"
    assert [s["id"] for s in client.get("/api/selfcare/sessions?range=1W").json()] == [sid]
    due = client.get("/api/selfcare/due").json()
    assert [(d["type_key"], d["status"]) for d in due][:2] == [("exfoliation", "never"), ("am_routine", "due")]
    bad = client.post("/api/selfcare/sessions", json={"category": "skincare", "types": []})
    assert bad.status_code == 422
    assert client.delete(f"/api/selfcare/sessions/{sid}").status_code == 204


def test_calendar_and_last_done(client):
    client.post("/api/selfcare/sessions", json={"category": "skincare", "types": ["am_routine"]})
    days = client.get("/api/calendar?from=2026-09-01&to=2026-09-30&kinds=workout,selfcare").json()
    assert days == [{"date": "2026-09-22", "entries": [
        {"kind": "selfcare", "id": 1, "title": "Skincare (Face)", "summary": "AM routine", "in_progress": False}]}]
    assert client.get("/api/calendar?from=2026-09-30&to=2026-09-01&kinds=workout").status_code == 422
    assert client.get("/api/calendar/last-done").json()["selfcare"] == "2026-09-22"


def test_ui_not_mounted_without_build(client):
    assert client.get("/ui/").status_code == 404
    assert client.get("/", follow_redirects=False).headers["location"] == "/ui/"
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_api.py -q`
Expected: FAIL — 404s on `/api/today`, `/api/catalog`, etc.

- [ ] **Step 4: Replace `core/api.py` with the full version**

```python
"""HTTP surface: everything under /api, the built UI at /ui.

One `_build_<area>_router()` per area. Domain errors map to their status with
the message as `detail`. Values cross the API in display units (Settings:
lb/kg, mi/km; durations in seconds); conversion happens here, at the edge,
so services stay in SI.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, FastAPI, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.container import Services
from schemas.calendar import CalendarDay, LastDone
from schemas.selfcare import DueItem, LogSelfcareIn, SelfcareSessionOut, UpdateSelfcareIn
from schemas.workouts import (
    AddExerciseIn,
    ExerciseOut,
    FinishOut,
    SetOut,
    SetPatch,
    StartWorkoutIn,
    WorkoutOut,
    WorkoutSummary,
)
from services import preferences
from services.errors import AppError, Invalid
from services.units import UnitPrefs, from_storage, to_storage

RangeKey = Literal["1W", "1M", "1Y"]


def _svc(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def _units(s: Services) -> UnitPrefs:
    return preferences.unit_prefs(s.db, s.catalog.apollo.settings_defaults)


# ------------------------------------------------------------------ unit edge


def _set_view(item: SetOut, prefs: UnitPrefs) -> SetOut:
    return item.model_copy(
        update={
            "weight": from_storage("weight", item.weight, prefs),
            "distance": from_storage("distance", item.distance, prefs),
        }
    )


def _exercise_view(ex: ExerciseOut, prefs: UnitPrefs) -> ExerciseOut:
    return ex.model_copy(update={"sets": [_set_view(x, prefs) for x in ex.sets]})


def _workout_view(w: WorkoutOut, prefs: UnitPrefs) -> WorkoutOut:
    return w.model_copy(update={"exercises": [_exercise_view(e, prefs) for e in w.exercises]})


def _patch_to_si(patch: SetPatch, prefs: UnitPrefs) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for field, value in patch.model_dump(exclude_unset=True).items():
        if field == "done":
            out[field] = value
            continue
        try:
            out[field] = to_storage(field, value, prefs)
        except ValueError as exc:
            raise Invalid(str(exc)) from exc
    return out


# ------------------------------------------------------------------ routers


def _build_meta_router() -> APIRouter:
    router = APIRouter(tags=["meta"])

    @router.get("/health")
    def health(request: Request) -> dict[str, Any]:
        s = _svc(request)
        errors = list(s.catalog.errors)
        return {"status": "degraded" if errors else "ok", "config_errors": errors}

    @router.get("/today")
    def today(request: Request) -> dict[str, str]:
        return {"today": _svc(request).clock.today().isoformat()}

    @router.get("/catalog")
    def catalog(request: Request) -> dict[str, Any]:
        c = _svc(request).catalog
        return {
            "metric_types": {k: list(v.fields) for k, v in c.exercises.metric_types.items()},
            "muscle_groups": list(c.exercises.muscle_groups),
            "exercises_by_group": {
                group: [
                    {"key": e.key, "name": e.name, "type": e.type, "groups": e.muscle_groups}
                    for e in exercises
                ]
                for group, exercises in c.exercises_by_group().items()
            },
            "selfcare": [
                {
                    "key": cat.key,
                    "name": cat.name,
                    "types": [{"key": t.key, "name": t.name, "every_days": t.every_days} for t in cat.types],
                }
                for cat in c.selfcare.categories
            ],
            "colors": c.apollo.colors.model_dump(),
        }

    return router


class SettingIn(BaseModel):
    value: str


def _build_settings_router() -> APIRouter:
    router = APIRouter(prefix="/settings", tags=["settings"])

    @router.get("")
    def get_settings(request: Request) -> dict[str, str]:
        s = _svc(request)
        return preferences.get_all(s.db, s.catalog.apollo.settings_defaults)

    @router.put("/{key}", status_code=status.HTTP_204_NO_CONTENT)
    def put_setting(key: str, body: SettingIn, request: Request) -> Response:
        s = _svc(request)
        preferences.set_pref(s.db, key, body.value, s.clock.now_iso())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _build_workouts_router() -> APIRouter:
    router = APIRouter(tags=["workouts"])

    @router.post("/workouts", status_code=status.HTTP_201_CREATED)
    def start(body: StartWorkoutIn, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.start(body.planned_exercises), _units(s))

    @router.get("/workouts/open")
    def get_open(request: Request) -> WorkoutOut | None:
        s = _svc(request)
        w = s.workouts.get_open()
        return _workout_view(w, _units(s)) if w else None

    @router.get("/workouts")
    def history(request: Request, range: RangeKey = "1M") -> list[WorkoutSummary]:
        return _svc(request).workouts.history(range)

    @router.get("/workouts/{workout_id}")
    def get_workout(workout_id: int, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.get(workout_id), _units(s))

    @router.post("/workouts/{workout_id}/exercises", status_code=status.HTTP_201_CREATED)
    def add_exercise(workout_id: int, body: AddExerciseIn, request: Request) -> ExerciseOut:
        s = _svc(request)
        return _exercise_view(s.workouts.add_exercise(workout_id, body.exercise_key), _units(s))

    @router.delete("/workouts/{workout_id}/exercises/{we_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_exercise(workout_id: int, we_id: int, request: Request) -> Response:
        _svc(request).workouts.remove_exercise(workout_id, we_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/workouts/{workout_id}/exercises/{we_id}/sets", status_code=status.HTTP_201_CREATED)
    def add_set(workout_id: int, we_id: int, request: Request) -> SetOut:
        s = _svc(request)
        return _set_view(s.workouts.add_set(workout_id, we_id), _units(s))

    @router.patch("/sets/{set_id}")
    def update_set(set_id: int, body: SetPatch, request: Request) -> SetOut:
        s = _svc(request)
        prefs = _units(s)
        return _set_view(s.workouts.update_set(set_id, _patch_to_si(body, prefs)), prefs)

    @router.delete("/sets/{set_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_set(set_id: int, request: Request) -> Response:
        _svc(request).workouts.delete_set(set_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/workouts/{workout_id}/finish")
    def finish(workout_id: int, request: Request, end_at_last_activity: bool = False) -> FinishOut:
        s = _svc(request)
        w = s.workouts.finish(workout_id, end_at_last_activity)
        return FinishOut(workout=_workout_view(w, _units(s)) if w else None, deleted=w is None)

    @router.post("/workouts/{workout_id}/reopen")
    def reopen(workout_id: int, request: Request) -> WorkoutOut:
        s = _svc(request)
        return _workout_view(s.workouts.reopen(workout_id), _units(s))

    @router.delete("/workouts/{workout_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_workout(workout_id: int, request: Request) -> Response:
        _svc(request).workouts.delete(workout_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


def _build_selfcare_router() -> APIRouter:
    router = APIRouter(prefix="/selfcare", tags=["selfcare"])

    @router.post("/sessions", status_code=status.HTTP_201_CREATED)
    def log(body: LogSelfcareIn, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.log(body.category, body.types, body.date, body.notes)

    @router.get("/sessions")
    def history(request: Request, range: RangeKey = "1M", category: str | None = None) -> list[SelfcareSessionOut]:
        return _svc(request).selfcare.history(range, category)

    @router.get("/sessions/{session_id}")
    def get_session(session_id: int, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.get(session_id)

    @router.patch("/sessions/{session_id}")
    def update(session_id: int, body: UpdateSelfcareIn, request: Request) -> SelfcareSessionOut:
        return _svc(request).selfcare.update(session_id, body.model_dump(exclude_unset=True))

    @router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(session_id: int, request: Request) -> Response:
        _svc(request).selfcare.delete(session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.get("/due")
    def due(request: Request) -> list[DueItem]:
        return _svc(request).selfcare.due_list()

    return router


def _build_calendar_router() -> APIRouter:
    router = APIRouter(prefix="/calendar", tags=["calendar"])

    @router.get("")
    def entries(
        request: Request,
        from_: date = Query(alias="from"),
        to: date = Query(),
        kinds: str = "workout,selfcare",
    ) -> list[CalendarDay]:
        wanted = {k.strip() for k in kinds.split(",") if k.strip()}
        return _svc(request).calendar.entries(from_, to, wanted)

    @router.get("/last-done")
    def last_done(request: Request) -> LastDone:
        return _svc(request).calendar.last_done()

    return router


# ------------------------------------------------------------------ app


def create_app(services: Services, *, lifespan: Any = None, mount_static: bool = True) -> FastAPI:
    app = FastAPI(title="Apollo", lifespan=lifespan)
    app.state.services = services

    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": str(exc)})

    api = APIRouter(prefix="/api")
    for build in (
        _build_meta_router,
        _build_settings_router,
        _build_workouts_router,
        _build_selfcare_router,
        _build_calendar_router,
    ):
        api.include_router(build())
    app.include_router(api)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/ui/")

    web_dir = Path(services.settings.WEB_DIR)
    if mount_static and web_dir.is_dir():
        app.mount("/ui", StaticFiles(directory=web_dir, html=True), name="ui")

    return app
```

- [ ] **Step 5: Run the API tests**

Run: `uv run pytest tests/test_api.py -q`
Expected: `10 passed`

- [ ] **Step 6: Run the whole suite and the server**

Run: `uv run pytest -q`
Expected: all pass, 0 failures.

Run:
```bash
PORT=8777 uv run python main.py &
sleep 2
curl -s localhost:8777/api/health; echo
curl -s localhost:8777/api/catalog | head -c 200; echo
kill %1
```
Expected: `{"status":"ok","config_errors":[]}` and the start of the catalog JSON. (This writes `./apollo.db`, which is gitignored.)

- [ ] **Step 7: Commit**

```bash
git add core/api.py tests/conftest.py tests/test_api.py
git commit -m "feat: /api routes for workouts, self-care, calendar and settings"
```

---

### Task 15: Final verification

- [ ] **Step 1: Clean build and full test run**

```bash
make clean && make build && make test
```
Expected: build completes; all tests pass.

- [ ] **Step 2: Check `/docs` renders** — `make run` in one terminal, open `http://localhost:8000/docs`, confirm every route from spec §6 plus `/api/today` is listed. Stop the server.

- [ ] **Step 3: Confirm the tree matches the file map** — `git status` is clean; `ls services core schemas config tests` shows the files in the File map above.

The backend is complete. Continue with `docs/2026-09-22-mvp-frontend-plan.md`.
