from pathlib import Path

from services.catalog import load_catalog

REPO_CONFIG = Path(__file__).resolve().parent.parent / "config"


def _write(d: Path, apollo: str = "", exercises: str = "", selfcare: str = "") -> Path:
    d.mkdir(exist_ok=True)
    (d / "apollo.yaml").write_text(apollo)
    (d / "exercises.yaml").write_text(exercises)
    (d / "selfcare.yaml").write_text(selfcare)
    return d


EXERCISES = """
metric_types: {weight_reps: {fields: [weight, reps]}, time: {fields: [duration]}}
muscle_groups: [chest, legs, glutes, core]
exercises:
  - {key: bench_press, name: Bench, group: chest, type: weight_reps}
  - {key: squat, name: Squat, groups: [legs, glutes], type: weight_reps}
  - {key: plank, name: Plank, group: core, type: time}
"""

SELFCARE = """
categories:
  - key: skincare
    name: Skincare (Face)
    types: [{key: am_routine, name: AM routine, every_days: 1}]
"""


def test_repo_config_is_valid():
    catalog = load_catalog(REPO_CONFIG)
    assert catalog.errors == ()
    assert catalog.exercise("bench_press") is not None


def test_lookups(tmp_path):
    c = load_catalog(_write(tmp_path / "c", exercises=EXERCISES, selfcare=SELFCARE))
    assert c.errors == ()
    assert c.exercise("squat").name == "Squat"
    assert c.exercise("nope") is None
    assert c.fields_for("weight_reps") == ["weight", "reps"]
    by_group = c.exercises_by_group()
    assert list(by_group) == ["chest", "legs", "glutes", "core"]
    assert [e.key for e in by_group["glutes"]] == ["squat"]
    assert c.category("skincare").name == "Skincare (Face)"
    assert c.selfcare_type("skincare", "am_routine").every_days == 1
    assert c.selfcare_type("skincare", "nope") is None


def test_empty_files_fall_back_to_defaults(tmp_path):
    c = load_catalog(_write(tmp_path / "c"))
    assert c.errors == ()
    assert c.apollo.timezone == "UTC"
    assert c.exercises.exercises == []


def test_missing_file_reported(tmp_path):
    d = _write(tmp_path / "c", exercises=EXERCISES)
    (d / "selfcare.yaml").unlink()
    c = load_catalog(d)
    assert c.errors == ("selfcare.yaml: file not found",)
    assert c.selfcare.categories == []


def test_unreadable_file_reported_and_others_still_load(tmp_path):
    d = _write(tmp_path / "c", exercises=EXERCISES, selfcare=SELFCARE)
    (d / "apollo.yaml").unlink()
    (d / "apollo.yaml").mkdir()
    c = load_catalog(d)
    assert len(c.errors) == 1
    assert c.errors[0].startswith("apollo.yaml: cannot read (")
    assert c.apollo.timezone == "UTC"
    assert c.category("skincare") is not None


def test_invalid_file_reported_with_location_and_others_still_load(tmp_path):
    bad = EXERCISES.replace("type: time", "type: nope")
    c = load_catalog(_write(tmp_path / "c", exercises=bad, selfcare=SELFCARE))
    assert len(c.errors) == 1
    assert c.errors[0].startswith("exercises.yaml: ")
    assert "unknown type 'nope'" in c.errors[0]
    assert c.exercises.exercises == []          # the broken file falls back to empty
    assert c.category("skincare") is not None   # the good ones still load


def test_yaml_syntax_error_reported(tmp_path):
    c = load_catalog(_write(tmp_path / "c", apollo="timezone: [unclosed"))
    assert c.errors[0].startswith("apollo.yaml: ")


def test_non_mapping_top_level_reported(tmp_path):
    c = load_catalog(_write(tmp_path / "c", apollo="- a list"))
    assert c.errors == ("apollo.yaml: top level must be a mapping",)


def test_duplicate_top_level_key_reported(tmp_path):
    apollo = "timezone: America/New_York\ntimezone: America/Chicago\n"
    c = load_catalog(_write(tmp_path / "c", apollo=apollo, exercises=EXERCISES, selfcare=SELFCARE))
    assert len(c.errors) == 1
    assert c.errors[0].startswith("apollo.yaml: ")
    assert "timezone" in c.errors[0]
    assert c.exercise("bench_press") is not None   # the good ones still load


def test_duplicate_nested_key_reported(tmp_path):
    bad = """
metric_types: {weight_reps: {fields: [weight, reps]}}
muscle_groups: [chest]
exercises:
  - key: bench_press
    name: Bench
    name: Other
    group: chest
    type: weight_reps
"""
    c = load_catalog(_write(tmp_path / "c", exercises=bad, selfcare=SELFCARE))
    assert len(c.errors) == 1
    assert c.errors[0].startswith("exercises.yaml: ")
    assert "name" in c.errors[0]
    assert c.category("skincare") is not None      # the good ones still load
