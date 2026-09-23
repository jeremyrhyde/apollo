from __future__ import annotations

import datetime as dt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

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

    @model_validator(mode="after")
    def _date_not_explicit_null(self) -> "UpdateSelfcareIn":
        # `date` is omittable (unchanged) but not nullable: an explicit
        # `"date": null` would otherwise reset the session to today.
        if "date" in self.model_fields_set and self.date is None:
            raise ValueError("date must not be null")
        return self


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
