"""Settings-tab preferences (the Hermes pattern).

Seeded from apollo.yaml `settings_defaults` on first run; after that the
database is authoritative and YAML edits to these keys are ignored.
Allowed values are read from the SettingsDefaults Literal types, so the YAML
schema and this validator can never disagree.
"""

from __future__ import annotations

from typing import get_args

from core.state import Database
from schemas.config import SettingsDefaults
from services.errors import Invalid
from services.units import UnitPrefs

ALLOWED: dict[str, tuple[str, ...]] = {
    name: get_args(field.annotation) for name, field in SettingsDefaults.model_fields.items()
}


def seed(db: Database, defaults: SettingsDefaults, now_iso: str) -> None:
    with db.tx() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO preferences (key, value, updated_at) VALUES (?, ?, ?)",
            [(key, value, now_iso) for key, value in defaults.model_dump().items()],
        )


def get_all(db: Database, defaults: SettingsDefaults) -> dict[str, str]:
    stored = {r["key"]: r["value"] for r in db.query("SELECT key, value FROM preferences")}
    return {key: stored.get(key, value) for key, value in defaults.model_dump().items()}


def set_pref(db: Database, key: str, value: str, now_iso: str) -> None:
    if key not in ALLOWED:
        raise Invalid(f"unknown setting {key!r}")
    if value not in ALLOWED[key]:
        raise Invalid(f"{key} must be one of: {', '.join(ALLOWED[key])}")
    with db.tx() as conn:
        conn.execute(
            "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now_iso),
        )


def unit_prefs(db: Database, defaults: SettingsDefaults) -> UnitPrefs:
    prefs = get_all(db, defaults)
    return UnitPrefs(weight_unit=prefs["weight_unit"], distance_unit=prefs["distance_unit"])
