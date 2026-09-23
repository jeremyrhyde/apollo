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
