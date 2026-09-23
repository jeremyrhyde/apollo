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
