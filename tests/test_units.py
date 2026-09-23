import pytest

from services.units import STORAGE_COLUMNS, UnitPrefs, from_storage, to_storage

LB = UnitPrefs(weight_unit="lb", distance_unit="mi")
KG = UnitPrefs(weight_unit="kg", distance_unit="km")


def test_weight_round_trip_lb():
    kg = to_storage("weight", 135, LB)
    assert kg == pytest.approx(61.2349, abs=1e-4)
    assert from_storage("weight", kg, LB) == 135.0


def test_weight_kg_is_identity():
    assert to_storage("weight", 60, KG) == 60.0
    assert from_storage("weight", 60.0, KG) == 60.0


def test_distance():
    assert to_storage("distance", 3.1, LB) == pytest.approx(4988.97, abs=0.01)
    assert from_storage("distance", 5000.0, LB) == 3.107
    assert to_storage("distance", 5, KG) == 5000.0
    assert from_storage("distance", 5000.0, KG) == 5.0


def test_reps_and_duration():
    assert to_storage("reps", 8, LB) == 8
    assert to_storage("reps", 8.0, LB) == 8
    with pytest.raises(ValueError):
        to_storage("reps", 8.5, LB)
    assert to_storage("duration", 59.6, LB) == 60
    assert from_storage("duration", 60, LB) == 60


def test_none_passes_through():
    for field in STORAGE_COLUMNS:
        assert to_storage(field, None, LB) is None
        assert from_storage(field, None, LB) is None


def test_unknown_field():
    with pytest.raises(KeyError):
        to_storage("speed", 1, LB)
