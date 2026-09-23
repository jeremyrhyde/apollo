from datetime import UTC, datetime

import pytest

from services.errors import Conflict, Invalid, NotFound
from services.workouts import WorkoutService


@pytest.fixture
def workouts(env):
    return WorkoutService(env.db, env.catalog, env.clock, env.bus, stale_hours=12)


def log_exercise(workouts, workout_id, key, values):
    """Add `key` and log one done set per dict in `values` (SI units)."""
    ex = workouts.add_exercise(workout_id, key)
    set_ids = [ex.sets[0].id] + [workouts.add_set(workout_id, ex.id).id for _ in values[1:]]
    for set_id, vals in zip(set_ids, values):
        workouts.update_set(set_id, {**vals, "done": True})
    return ex.id


def test_start_creates_open_workout(workouts):
    w = workouts.start([])
    assert w.ended_at is None
    assert w.local_date == "2026-09-22"
    assert w.exercises == [] and w.focus == []
    assert workouts.get_open().id == w.id


def test_no_open_workout(workouts):
    assert workouts.get_open() is None


def test_start_twice_conflicts(workouts):
    workouts.start([])
    with pytest.raises(Conflict, match="already in progress"):
        workouts.start([])


def test_start_with_planned_exercises(workouts):
    w = workouts.start(["bench_press", "run"])
    assert [e.exercise_key for e in w.exercises] == ["bench_press", "run"]
    assert all(e.planned for e in w.exercises)


def test_start_with_unknown_planned_exercise_creates_nothing(workouts):
    with pytest.raises(Invalid, match="unknown exercise 'nope'"):
        workouts.start(["bench_press", "nope"])
    assert workouts.get_open() is None


def test_add_exercise_snapshots_catalog(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "squat")
    assert ex.name == "Back Squat"
    assert ex.metric_type == "weight_reps"
    assert ex.fields == ["weight", "reps"]
    assert ex.muscle_groups == ["legs", "glutes"]
    assert ex.planned is False
    assert [(s.done, s.weight, s.reps) for s in ex.sets] == [(False, None, None)]
    assert workouts.get(w.id).focus == ["legs", "glutes"]


def test_add_unknown_exercise_invalid(workouts):
    w = workouts.start([])
    with pytest.raises(Invalid):
        workouts.add_exercise(w.id, "nope")


def test_prefill_copies_done_sets_from_last_finished_workout(workouts, now):
    w1 = workouts.start([])
    log_exercise(workouts, w1.id, "bench_press", [{"weight": 60.0, "reps": 8}, {"weight": 62.5, "reps": 6}])
    workouts.finish(w1.id)
    now.advance(days=2)
    w2 = workouts.start([])
    ex = workouts.add_exercise(w2.id, "bench_press")
    assert [(s.weight, s.reps, s.done) for s in ex.sets] == [(60.0, 8, False), (62.5, 6, False)]


def test_prefill_ignores_the_open_workout(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "bench_press", [{"weight": 60.0, "reps": 8}])
    again = workouts.add_exercise(w.id, "bench_press")
    assert [(s.weight, s.reps) for s in again.sets] == [(None, None)]


def test_prefill_prefers_the_newer_workout_when_started_at_ties(workouts, env):
    # finish() doesn't exist yet (Task 10), so mark workouts finished directly.
    # bench_press sits at a *higher* position in the older workout than in the
    # newer one, so a tie-break that compares position before workout id would
    # (wrongly) still pick the older workout.
    w1 = workouts.start([])
    log_exercise(workouts, w1.id, "squat", [{"weight": 80.0, "reps": 5}])
    log_exercise(workouts, w1.id, "bench_press", [{"weight": 40.0, "reps": 10}])
    with env.db.tx() as conn:
        conn.execute("UPDATE workout SET ended_at = started_at WHERE id = ?", (w1.id,))

    w2 = workouts.start([])  # same `now` as w1 -> identical started_at
    log_exercise(workouts, w2.id, "bench_press", [{"weight": 70.0, "reps": 3}])
    with env.db.tx() as conn:
        conn.execute("UPDATE workout SET ended_at = started_at WHERE id = ?", (w2.id,))

    w3 = workouts.start([])
    ex = workouts.add_exercise(w3.id, "bench_press")
    assert [(s.weight, s.reps) for s in ex.sets] == [(70.0, 3)]


def test_add_set_copies_previous_values(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "bench_press")
    workouts.update_set(ex.sets[0].id, {"weight": 50.0, "reps": 5})
    new = workouts.add_set(w.id, ex.id)
    assert (new.position, new.weight, new.reps, new.done) == (2, 50.0, 5, False)


def test_add_set_to_exercise_of_another_workout_is_not_found(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(NotFound):
        workouts.add_set(w.id + 1, ex.id)


def test_update_set_rejects_fields_outside_metric_type(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(Invalid, match="weight does not apply to Plank"):
        workouts.update_set(ex.sets[0].id, {"weight": 10.0})
    assert workouts.update_set(ex.sets[0].id, {"duration": 60}).duration == 60


def test_update_set_rejects_unknown_keys_and_null_done(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "plank")
    with pytest.raises(Invalid):
        workouts.update_set(ex.sets[0].id, {"speed": 3})
    with pytest.raises(Invalid):
        workouts.update_set(ex.sets[0].id, {"done": None})


def test_toggle_done_and_undo(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "pull_up")
    sid = ex.sets[0].id
    assert workouts.update_set(sid, {"reps": 10, "done": True}).done is True
    assert workouts.update_set(sid, {"done": False}).done is False


def test_update_missing_set_not_found(workouts):
    with pytest.raises(NotFound):
        workouts.update_set(999, {"done": True})


def test_delete_set_and_exercise(workouts):
    w = workouts.start([])
    ex = workouts.add_exercise(w.id, "bench_press")
    second = workouts.add_set(w.id, ex.id)
    workouts.delete_set(second.id)
    assert len(workouts.get(w.id).exercises[0].sets) == 1
    workouts.remove_exercise(w.id, ex.id)
    assert workouts.get(w.id).exercises == []


def test_get_missing_workout_not_found(workouts):
    with pytest.raises(NotFound):
        workouts.get(42)


def test_finish_drops_undone_sets_and_empty_exercises(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "bench_press", [{"weight": 60.0, "reps": 8}])
    bench = workouts.get(w.id).exercises[0]
    workouts.add_set(w.id, bench.id)              # second set, never ticked
    workouts.add_exercise(w.id, "plank")          # exercise with nothing ticked
    result = workouts.finish(w.id)
    assert result is not None and result.ended_at is not None
    assert [e.exercise_key for e in result.exercises] == ["bench_press"]
    assert len(result.exercises[0].sets) == 1


def test_finish_with_nothing_done_deletes_the_workout(workouts):
    w = workouts.start([])
    workouts.add_exercise(w.id, "plank")
    assert workouts.finish(w.id) is None
    with pytest.raises(NotFound):
        workouts.get(w.id)


def test_finish_publishes_event(env, workouts):
    seen = []
    env.bus.subscribe("workout.finished", lambda name, payload: seen.append(payload))
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    assert seen == [{"id": w.id}]


def test_finish_at_last_activity(workouts, now):
    w = workouts.start([])
    now.advance(minutes=10)
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    now.advance(hours=20)
    result = workouts.finish(w.id, end_at_last_activity=True)
    assert result.ended_at == "2026-09-22T18:10:00+00:00"


def test_finish_twice_conflicts(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    with pytest.raises(Conflict):
        workouts.finish(w.id)


def test_reopen_edit_and_refinish(workouts, now):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    now.advance(days=1)
    reopened = workouts.reopen(w.id)
    assert reopened.ended_at is None and reopened.local_date == "2026-09-22"
    workouts.update_set(reopened.exercises[0].sets[0].id, {"reps": 12})
    again = workouts.finish(w.id)
    assert again.exercises[0].sets[0].reps == 12


def test_reopen_conflicts_when_another_is_open(workouts):
    w = workouts.start([])
    log_exercise(workouts, w.id, "pull_up", [{"reps": 10}])
    workouts.finish(w.id)
    workouts.start([])
    with pytest.raises(Conflict):
        workouts.reopen(w.id)


def test_reopen_open_workout_conflicts(workouts):
    w = workouts.start([])
    with pytest.raises(Conflict):
        workouts.reopen(w.id)


def test_delete_workout(workouts):
    w = workouts.start([])
    workouts.delete(w.id)
    assert workouts.get_open() is None
    with pytest.raises(NotFound):
        workouts.delete(w.id)


def test_focus_first_appearance_order(workouts):
    w = workouts.start([])
    for key in ("bench_press", "barbell_row", "bench_press", "squat"):
        workouts.add_exercise(w.id, key)
    assert workouts.get(w.id).focus == ["chest", "back", "legs", "glutes"]


def test_history_ranges_and_summary(workouts, now):
    def finished_on(dt, key="pull_up"):
        now.dt = dt
        w = workouts.start([])
        log_exercise(workouts, w.id, key, [{"reps": 10}, {"reps": 8}])
        now.advance(minutes=45)
        workouts.finish(w.id)
        return w.id

    old = finished_on(datetime(2026, 8, 13, 18, 0, tzinfo=UTC))    # 40 days before
    mid = finished_on(datetime(2026, 9, 12, 18, 0, tzinfo=UTC))    # 10 days before
    new = finished_on(datetime(2026, 9, 22, 18, 0, tzinfo=UTC), "bench_press")
    workouts.start([])                                             # open — never listed
    assert [s.id for s in workouts.history("1W")] == [new]
    assert [s.id for s in workouts.history("1M")] == [new, mid]
    assert [s.id for s in workouts.history("1Y")] == [new, mid, old]
    summary = workouts.history("1W")[0]
    assert (summary.duration_s, summary.focus, summary.exercise_count, summary.set_count) == (2700, ["chest"], 1, 2)


def test_get_open_flags_stale(workouts, now):
    workouts.start([])
    assert workouts.get_open().stale is False
    now.advance(hours=13)
    assert workouts.get_open().stale is True
