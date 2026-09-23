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
    reopened: bool = False  # a finished workout opened again for editing
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
