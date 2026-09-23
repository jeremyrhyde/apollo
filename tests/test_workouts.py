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
    w1 = workouts.start([])
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
