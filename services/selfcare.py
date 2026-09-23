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
            if "types" in changes:
                cat = self._category(row["category_key"])
                keys = self._check_types(cat, changes["types"] or [])
                conn.execute("DELETE FROM selfcare_session_type WHERE session_id = ?", (session_id,))
                self._insert_types(conn, session_id, cat, keys)
            if "date" in changes:
                new_date = changes["date"]
                if new_date is None:
                    raise Invalid("date must not be null")
                if new_date != date.fromisoformat(row["local_date"]):
                    local_date, performed_at = self._when(new_date)
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
            self._category(category)
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
