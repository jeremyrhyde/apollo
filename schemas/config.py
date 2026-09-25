"""Pydantic models for the three YAML files in config/.

Strict on purpose: unknown keys are errors, so a typo in a YAML file is
reported at boot instead of silently ignored. Cross-references (an exercise's
type and muscle groups) are checked here too, and every problem is reported,
not just the first.
"""

from __future__ import annotations

import re
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    ValidationInfo,
    field_validator,
    model_validator,
)

FieldName = Literal["weight", "reps", "distance", "duration"]
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# The highlightable regions of the body-map asset (see
# docs/2026-09-25-muscle-map-spec.md). `head`, `neck`, `knees` and the soleus
# regions are part of the silhouette but not selectable, so they're absent.
Muscle = Literal[
    "biceps", "triceps", "forearm",
    "front-deltoids", "back-deltoids",
    "chest", "abs", "obliques",
    "trapezius", "upper-back", "lower-back",
    "quadriceps", "hamstring", "gluteal", "adductor", "abductors", "calves",
]


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


class ExerciseMuscles(_Strict):
    primary: list[Muscle] = Field(min_length=1)
    secondary: list[Muscle] = []

    @model_validator(mode="after")
    def _no_duplicates_or_overlap(self) -> "ExerciseMuscles":
        errors: list[str] = []
        if len(set(self.primary)) != len(self.primary):
            errors.append("primary must not repeat a muscle")
        if len(set(self.secondary)) != len(self.secondary):
            errors.append("secondary must not repeat a muscle")
        overlap = sorted(set(self.primary) & set(self.secondary))
        if overlap:
            errors.append(f"muscle(s) in both primary and secondary: {', '.join(overlap)}")
        if errors:
            raise ValueError("; ".join(errors))
        return self


class Exercise(_Strict):
    key: str
    name: str = Field(min_length=1)
    group: str | None = None
    groups: list[str] | None = None
    type: str
    muscles: ExerciseMuscles | None = None

    @field_validator("key")
    @classmethod
    def _key(cls, value: str) -> str:
        return _check_key(value)

    @field_validator("muscles", mode="before")
    @classmethod
    def _muscles_named(cls, value: Any, info: ValidationInfo) -> Any:
        if value is None or isinstance(value, ExerciseMuscles):
            return value
        try:
            return ExerciseMuscles.model_validate(value)
        except ValidationError as exc:
            key = info.data.get("key", "?")
            detail = "; ".join(err["msg"].removeprefix("Value error, ") for err in exc.errors())
            raise ValueError(f"exercise {key!r}: {detail}") from exc

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
