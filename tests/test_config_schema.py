import pytest
from pydantic import ValidationError

from schemas.config import ApolloFile, ExerciseMuscles, ExercisesFile, SelfcareFile

EX_OK = {
    "metric_types": {"weight_reps": {"fields": ["weight", "reps"]}, "time": {"fields": ["duration"]}},
    "muscle_groups": ["chest", "legs", "glutes", "core"],
    "exercises": [
        {"key": "bench_press", "name": "Bench Press", "group": "chest", "type": "weight_reps"},
        {"key": "squat", "name": "Squat", "groups": ["legs", "glutes"], "type": "weight_reps"},
        {"key": "plank", "name": "Plank", "group": "core", "type": "time"},
    ],
}


def test_valid_exercises_file():
    f = ExercisesFile.model_validate(EX_OK)
    assert [e.muscle_groups for e in f.exercises] == [["chest"], ["legs", "glutes"], ["core"]]


def test_unknown_top_level_key_rejected():
    with pytest.raises(ValidationError):
        ExercisesFile.model_validate({**EX_OK, "extra": 1})


def test_group_and_groups_are_exclusive():
    bad = {**EX_OK, "exercises": [{"key": "x", "name": "X", "group": "chest", "groups": ["legs"], "type": "time"}]}
    with pytest.raises(ValidationError, match="exactly one of"):
        ExercisesFile.model_validate(bad)


def test_unknown_type_and_group_named():
    bad = {**EX_OK, "exercises": [{"key": "x", "name": "X", "group": "arms", "type": "nope"}]}
    with pytest.raises(ValidationError) as exc:
        ExercisesFile.model_validate(bad)
    assert "unknown type 'nope'" in str(exc.value)
    assert "unknown muscle group 'arms'" in str(exc.value)


def test_duplicate_exercise_key():
    bad = {**EX_OK, "exercises": EX_OK["exercises"] + [EX_OK["exercises"][0]]}
    with pytest.raises(ValidationError, match="duplicate exercise key 'bench_press'"):
        ExercisesFile.model_validate(bad)


def test_bad_field_name_rejected():
    bad = {**EX_OK, "metric_types": {"weird": {"fields": ["speed"]}}}
    with pytest.raises(ValidationError):
        ExercisesFile.model_validate(bad)


def test_key_format_enforced():
    bad = {**EX_OK, "exercises": [{"key": "Bench Press", "name": "B", "group": "chest", "type": "time"}]}
    with pytest.raises(ValidationError, match="lowercase"):
        ExercisesFile.model_validate(bad)


def test_selfcare_every_days_must_be_positive():
    with pytest.raises(ValidationError):
        SelfcareFile.model_validate(
            {"categories": [{"key": "skincare", "name": "S", "types": [{"key": "a", "name": "A", "every_days": 0}]}]}
        )


def test_selfcare_duplicate_type_key():
    with pytest.raises(ValidationError, match="duplicate type key 'a'"):
        SelfcareFile.model_validate(
            {"categories": [{"key": "skincare", "name": "S", "types": [{"key": "a", "name": "A"}, {"key": "a", "name": "B"}]}]}
        )


# ------------------------------------------------------------------ muscles


def test_exercise_with_valid_muscles():
    ex = {**EX_OK["exercises"][0], "muscles": {"primary": ["chest"], "secondary": ["front-deltoids", "triceps"]}}
    f = ExercisesFile.model_validate({**EX_OK, "exercises": [ex]})
    assert f.exercises[0].muscles.primary == ["chest"]
    assert f.exercises[0].muscles.secondary == ["front-deltoids", "triceps"]


def test_exercise_without_muscles_defaults_to_none():
    f = ExercisesFile.model_validate(EX_OK)
    assert f.exercises[0].muscles is None


def test_unknown_muscle_name_rejected():
    ex = {**EX_OK["exercises"][0], "muscles": {"primary": ["lats"]}}
    with pytest.raises(ValidationError, match="exercise 'bench_press'"):
        ExercisesFile.model_validate({**EX_OK, "exercises": [ex]})


def test_empty_primary_rejected():
    ex = {**EX_OK["exercises"][0], "muscles": {"primary": []}}
    with pytest.raises(ValidationError, match="exercise 'bench_press'"):
        ExercisesFile.model_validate({**EX_OK, "exercises": [ex]})


def test_muscle_in_both_lists_rejected():
    ex = {**EX_OK["exercises"][0], "muscles": {"primary": ["chest"], "secondary": ["chest"]}}
    with pytest.raises(ValidationError, match=r"exercise 'bench_press'.*both primary and secondary.*chest"):
        ExercisesFile.model_validate({**EX_OK, "exercises": [ex]})


def test_duplicate_muscle_in_list_rejected():
    ex = {**EX_OK["exercises"][0], "muscles": {"primary": ["chest", "chest"]}}
    with pytest.raises(ValidationError, match="exercise 'bench_press'.*primary must not repeat"):
        ExercisesFile.model_validate({**EX_OK, "exercises": [ex]})


def test_exercise_muscles_rejects_unknown_extra_key():
    with pytest.raises(ValidationError):
        ExerciseMuscles.model_validate({"primary": ["chest"], "tertiary": ["abs"]})


def test_apollo_defaults_and_validation():
    assert ApolloFile().settings_defaults.calendar_view == "month"
    with pytest.raises(ValidationError, match="unknown timezone"):
        ApolloFile.model_validate({"timezone": "Mars/Olympus"})
    with pytest.raises(ValidationError):
        ApolloFile.model_validate({"colors": {"workout": "green"}})
    with pytest.raises(ValidationError):
        ApolloFile.model_validate({"day_start_hour": 24})
