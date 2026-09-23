import pytest

from core.state import Database
from schemas.config import SettingsDefaults
from services import preferences
from services.errors import Invalid
from services.units import UnitPrefs

NOW = "2026-09-22T18:00:00+00:00"


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "t.db"))
    database.migrate()
    yield database
    database.close()


def test_allowed_values_come_from_the_schema():
    assert preferences.ALLOWED["calendar_view"] == ("week", "month", "year")
    assert set(preferences.ALLOWED) == set(SettingsDefaults.model_fields)


def test_seed_only_on_first_run(db):
    preferences.seed(db, SettingsDefaults(calendar_view="week"), NOW)
    preferences.seed(db, SettingsDefaults(calendar_view="year"), NOW)
    assert preferences.get_all(db, SettingsDefaults())["calendar_view"] == "week"


def test_missing_rows_fall_back_to_defaults(db):
    assert preferences.get_all(db, SettingsDefaults(weight_unit="kg"))["weight_unit"] == "kg"


def test_set_validates(db):
    preferences.set_pref(db, "weight_unit", "kg", NOW)
    assert preferences.get_all(db, SettingsDefaults())["weight_unit"] == "kg"
    with pytest.raises(Invalid, match="must be one of"):
        preferences.set_pref(db, "weight_unit", "stone", NOW)
    with pytest.raises(Invalid, match="unknown setting"):
        preferences.set_pref(db, "theme", "dark", NOW)


def test_unit_prefs(db):
    preferences.seed(db, SettingsDefaults(weight_unit="kg", distance_unit="km"), NOW)
    assert preferences.unit_prefs(db, SettingsDefaults()) == UnitPrefs("kg", "km")


def test_invalid_stored_value_falls_back_to_default(db):
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            ("weight_unit", "stone", NOW),
        )
    assert preferences.get_all(db, SettingsDefaults())["weight_unit"] == "lb"
    assert preferences.unit_prefs(db, SettingsDefaults()).weight_unit == "lb"
