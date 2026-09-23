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
