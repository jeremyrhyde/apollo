"""SI storage ↔ display units.

Storage: weight kg, distance m, duration s, reps count. The API speaks the
user's display units (Settings: lb/kg, mi/km); durations are seconds on both
sides and formatted by the UI.
"""

from __future__ import annotations

from dataclasses import dataclass

LB_IN_KG = 0.45359237
MI_IN_M = 1609.344
KM_IN_M = 1000.0

STORAGE_COLUMNS = {
    "weight": "weight_kg",
    "reps": "reps",
    "distance": "distance_m",
    "duration": "duration_s",
}


@dataclass(frozen=True)
class UnitPrefs:
    weight_unit: str = "lb"
    distance_unit: str = "mi"


def _distance_factor(prefs: UnitPrefs) -> float:
    return MI_IN_M if prefs.distance_unit == "mi" else KM_IN_M


def to_storage(field: str, value: float | int | None, prefs: UnitPrefs) -> float | int | None:
    STORAGE_COLUMNS[field]  # KeyError for unknown fields
    if value is None:
        return None
    if field == "weight":
        return float(value) * LB_IN_KG if prefs.weight_unit == "lb" else float(value)
    if field == "distance":
        return float(value) * _distance_factor(prefs)
    if field == "reps":
        if float(value) != int(value):
            raise ValueError("reps must be a whole number")
        return int(value)
    return int(round(float(value)))  # duration


def from_storage(field: str, value: float | int | None, prefs: UnitPrefs) -> float | int | None:
    STORAGE_COLUMNS[field]
    if value is None:
        return None
    if field == "weight":
        shown = value / LB_IN_KG if prefs.weight_unit == "lb" else value
        return round(shown, 2)
    if field == "distance":
        return round(value / _distance_factor(prefs), 3)
    return int(value)
