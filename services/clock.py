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
