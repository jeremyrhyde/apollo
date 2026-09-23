import dataclasses
from datetime import date

import pytest

from schemas.config import SelfcareCategory, SelfcareFile, SelfcareType
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
        (5, date(2026, 9, 18), "soon", -1),     # ratio exactly 0.8 (boundary)
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


def test_update_same_date_keeps_performed_at(selfcare):
    """Resending the (unchanged) date must not shift performed_at or reorder the day."""
    s = selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 20))
    updated = selfcare.update(s.id, {"date": date(2026, 9, 20), "notes": "y"})
    assert updated.performed_at == s.performed_at
    assert updated.notes == "y"


def test_update_future_date_invalid(selfcare):
    s = selfcare.log("skincare", ["am_routine"])
    with pytest.raises(Invalid, match="future"):
        selfcare.update(s.id, {"date": date(2026, 9, 23)})


def test_update_null_date_invalid(selfcare):
    s = selfcare.log("skincare", ["am_routine"], on=date(2026, 9, 20))
    with pytest.raises(Invalid, match="null"):
        selfcare.update(s.id, {"date": None})


def test_update_unknown_type_rolls_back(selfcare):
    s = selfcare.log("skincare", ["am_routine"])
    with pytest.raises(Invalid, match="unknown type"):
        selfcare.update(s.id, {"types": ["nope"]})
    unchanged = selfcare.get(s.id)
    assert [t.key for t in unchanged.types] == ["am_routine"]


def test_update_missing_id_not_found(selfcare):
    with pytest.raises(NotFound):
        selfcare.update(999, {"notes": "x"})


def test_update_notes_only_after_category_removed(env, selfcare):
    """update/delete work on any session, any time — even if its category was
    later removed from selfcare.yaml (spec §5)."""
    s = selfcare.log("skincare", ["am_routine"])
    stripped = dataclasses.replace(env.catalog, selfcare=SelfcareFile(categories=[]))
    svc = SelfcareService(env.db, stripped, env.clock, env.bus)
    updated = svc.update(s.id, {"notes": "z"})
    assert updated.notes == "z"
    assert updated.category_name == "skincare"  # falls back to the key; no catalog entry to name it


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


def test_due_list_orders_overdue_due_soon_ok(env):
    catalog = dataclasses.replace(
        env.catalog,
        selfcare=SelfcareFile(
            categories=[
                SelfcareCategory(
                    key="c",
                    name="C",
                    types=[
                        SelfcareType(key="ok_t", name="Ok", every_days=5),
                        SelfcareType(key="soon_t", name="Soon", every_days=5),
                        SelfcareType(key="overdue_t", name="Overdue", every_days=5),
                        SelfcareType(key="due_t", name="Due", every_days=5),
                    ],
                )
            ]
        ),
    )
    svc = SelfcareService(env.db, catalog, env.clock, env.bus)
    svc.log("c", ["overdue_t"], on=date(2026, 9, 10))  # 12 days ago, ratio 2.4
    svc.log("c", ["due_t"], on=date(2026, 9, 17))       # 5 days ago, ratio 1.0
    svc.log("c", ["soon_t"], on=date(2026, 9, 18))      # 4 days ago, ratio 0.8
    svc.log("c", ["ok_t"], on=date(2026, 9, 21))        # 1 day ago, ratio 0.2
    items = svc.due_list()
    assert [(i.type_key, i.status) for i in items] == [
        ("overdue_t", "overdue"),
        ("due_t", "due"),
        ("soon_t", "soon"),
        ("ok_t", "ok"),
    ]
