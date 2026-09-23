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
        with self.db.tx() as conn:
            if conn.execute("SELECT 1 FROM workout WHERE ended_at IS NULL").fetchone():
                raise Conflict("a workout is already in progress")
            try:
                workout_id = conn.execute(
                    "INSERT INTO workout (started_at, local_date, created_at, updated_at) VALUES (?,?,?,?)",
                    (now, self.clock.today().isoformat(), now, now),
                ).lastrowid
            except sqlite3.IntegrityError as exc:
                raise Conflict("a workout is already in progress") from exc
            for key in planned_exercises:
                self._add_exercise(conn, workout_id, key, planned=True)
            return self._load(conn, workout_id)

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
                       ORDER BY w.started_at DESC, we.position DESC, w.id DESC LIMIT 1)
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
