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
    sid = selfcare.log("skincare", ["am_routine", "exfoliation"], on=date(2026, 9, 21)).id  # noon local = 19:00Z
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


def test_reopened_workout_not_in_progress(svc, now):
    workouts, _, calendar = svc
    wid = finished(workouts, now, datetime(2026, 9, 21, 17, 0, tzinfo=UTC), ["bench_press"])
    workouts.reopen(wid)
    entry = calendar.entries(date(2026, 9, 21), date(2026, 9, 21), {"workout"})[0].entries[0]
    assert entry.in_progress is False
    assert entry.summary == "1 exercise · 52 min"


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
