from datetime import UTC, date, datetime

import pytest

from services.errors import Invalid, NotFound
from services.selfcare import SelfcareService, compute_due

TODAY = date(2026, 9, 22)


@pytest.fixture
def selfcare(env):
    return SelfcareService(env.db, env.catalog, env.clock, env.bus)


# -------------------------------------------------------------- compute_due


def test_due_untracked_and_never():
    assert compute_due(None, date(2026, 9, 20), TODAY)["status"] == "untracked"
    assert compute_due(None, date(2026, 9, 20), TODAY)["days_since"] == 2
    assert compute_due(7, None, TODAY) == {
        "status": "never", "next_due": None, "days_since": None, "days_over": None, "ratio": None,
    }


@pytest.mark.parametrize(
    ("every", "last", "status", "days_over"),
    [
        (7, date(2026, 9, 21), "ok", -6),       # ratio 1/7
        (7, date(2026, 9, 16), "soon", -1),     # ratio 6/7 ≥ 0.8
        (7, date(2026, 9, 15), "due", 0),       # next_due == today
        (7, date(2026, 9, 11), "overdue", 4),
        (1, date(2026, 9, 22), "ok", -1),       # done today
        (1, date(2026, 9, 21), "due", 0),
    ],
)
def test_due_statuses(every, last, status, days_over):
    result = compute_due(every, last, TODAY)
    assert result["status"] == status
    assert result["days_over"] == days_over


# -------------------------------------------------------------- sessions


def test_log_defaults_to_today(selfcare):
    s = selfcare.log("skincare", ["am_routine", "face_mask"])
    assert s.local_date == "2026-09-22"
    assert s.performed_at == "2026-09-22T18:00:00+00:00"
    assert s.category_name == "Skincare (Face)"
    assert [(t.key, t.name) for t in s.types] == [("am_routine", "AM routine"), ("face_mask", "Face mask")]


def test_log_backdated_is_noon_local(selfcare):
    s = selfcare.log("skincare", ["exfoliation"], on=date(2026, 9, 20), notes="gentle")
    assert s.local_date == "2026-09-20"
    assert s.performed_at == "2026-09-20T19:00:00+00:00"
    assert s.notes == "gentle"


def test_log_validation(selfcare):
    with pytest.raises(Invalid, match="future"):
        selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 23))
    with pytest.raises(Invalid, match="unknown category"):
        selfcare.log("hair", ["am_routine"])
    with pytest.raises(Invalid, match="unknown type 'nope'"):
        selfcare.log("skincare", ["nope"])
    with pytest.raises(Invalid, match="at least one type"):
        selfcare.log("skincare", [])


def test_duplicate_types_are_collapsed(selfcare):
    s = selfcare.log("skincare", ["am_routine", "am_routine"])
    assert [t.key for t in s.types] == ["am_routine"]


def test_log_publishes_event(env, selfcare):
    seen = []
    env.bus.subscribe("selfcare.logged", lambda name, payload: seen.append(payload))
    s = selfcare.log("skincare", ["am_routine"])
    assert seen == [{"id": s.id, "category": "skincare", "types": ["am_routine"]}]


def test_update_and_delete(selfcare):
    s = selfcare.log("skincare", ["am_routine"])
    updated = selfcare.update(s.id, {"types": ["exfoliation"], "date": date(2026, 9, 21), "notes": "x"})
    assert [t.key for t in updated.types] == ["exfoliation"]
    assert (updated.local_date, updated.notes) == ("2026-09-21", "x")
    selfcare.delete(s.id)
    with pytest.raises(NotFound):
        selfcare.get(s.id)
    with pytest.raises(NotFound):
        selfcare.delete(s.id)


def test_history_range(selfcare):
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 22))
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 1))
    selfcare.log("skincare", ["am_routine"], on=date(2026, 3, 1))
    assert [s.local_date for s in selfcare.history("1W")] == ["2026-09-22"]
    assert [s.local_date for s in selfcare.history("1M")] == ["2026-09-22", "2026-09-01"]
    assert len(selfcare.history("1Y")) == 3
    assert selfcare.history("1Y", category="other") == []


def test_due_list_order_and_untracked_last(selfcare):
    selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 21))     # due today
    selfcare.log("skincare", ["face_mask"], on=date(2026, 9, 20))      # untracked
    items = selfcare.due_list()
    assert [(i.type_key, i.status) for i in items] == [
        ("exfoliation", "never"),
        ("am_routine", "due"),
        ("face_mask", "untracked"),
    ]
    assert items[1].last_done == "2026-09-21" and items[1].next_due == "2026-09-22"
    assert items[2].days_since == 2
