import sqlite3

import pytest

from core.state import MIGRATIONS_DIR, Database

TABLES = {
    "workout", "workout_exercise", "workout_exercise_group", "workout_set",
    "selfcare_session", "selfcare_session_type", "preferences", "schema_migrations",
}


@pytest.fixture
def db(tmp_path):
    database = Database(str(tmp_path / "t.db"))
    database.migrate()
    yield database
    database.close()


def _workout(conn, ended=None):
    return conn.execute(
        "INSERT INTO workout (started_at, ended_at, local_date, created_at, updated_at) VALUES (?,?,?,?,?)",
        ("2026-09-22T18:00:00+00:00", ended, "2026-09-22", "x", "x"),
    ).lastrowid


def test_migrate_creates_tables_and_is_idempotent(db):
    names = {r[0] for r in db.query("SELECT name FROM sqlite_master WHERE type='table'")}
    assert TABLES <= names
    latest = len(list(MIGRATIONS_DIR.glob("*.sql")))
    assert db.migrate() == latest
    assert db.query_one("SELECT COUNT(*) FROM schema_migrations")[0] == latest


def test_only_one_open_workout(db):
    with db.tx() as conn:
        _workout(conn)
        _workout(conn, ended="2026-09-22T19:00:00+00:00")
    with pytest.raises(sqlite3.IntegrityError):
        with db.tx() as conn:
            _workout(conn)


def test_tx_rolls_back_on_error(db):
    with pytest.raises(RuntimeError):
        with db.tx() as conn:
            _workout(conn)
            raise RuntimeError("boom")
    assert db.query_one("SELECT COUNT(*) FROM workout")[0] == 0


def test_foreign_keys_cascade(db):
    with db.tx() as conn:
        wid = _workout(conn)
        we = conn.execute(
            "INSERT INTO workout_exercise (workout_id, position, exercise_key, exercise_name, metric_type, metric_fields) "
            "VALUES (?,1,'bench_press','Bench','weight_reps','weight,reps')",
            (wid,),
        ).lastrowid
        conn.execute("INSERT INTO workout_set (workout_exercise_id, position, updated_at) VALUES (?,1,'x')", (we,))
        conn.execute("DELETE FROM workout WHERE id=?", (wid,))
    assert db.query_one("SELECT COUNT(*) FROM workout_set")[0] == 0


def test_rows_are_mappings(db):
    with db.tx() as conn:
        _workout(conn)
    row = db.query_one("SELECT local_date FROM workout")
    assert row["local_date"] == "2026-09-22"


def test_reopened_from_migration_applies_to_an_existing_db(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_initial.sql").write_text((MIGRATIONS_DIR / "001_initial.sql").read_text())
    database = Database(str(tmp_path / "old.db"))
    try:
        assert database.migrate(mig_dir) == 1
        with database.tx() as conn:
            workout_id = _workout(conn, ended="2026-09-22T19:00:00+00:00")
        assert database.migrate() >= 2
        columns = {r["name"] for r in database.query("PRAGMA table_info(workout)")}
        assert "reopened_from" in columns
        row = database.query_one("SELECT reopened_from FROM workout WHERE id = ?", (workout_id,))
        assert row["reopened_from"] is None
    finally:
        database.close()


def test_failed_migration_leaves_no_partial_schema(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "001_initial.sql").write_text((MIGRATIONS_DIR / "001_initial.sql").read_text())
    (mig_dir / "002_bad.sql").write_text("CREATE TABLE broken (id INTEGER); NOT VALID SQL;")
    database = Database(str(tmp_path / "bad.db"))
    try:
        with pytest.raises(sqlite3.Error):
            database.migrate(mig_dir)
        # 001 still applied cleanly; 002 recorded nothing and left no table.
        assert database.query_one("SELECT COUNT(*) FROM schema_migrations")[0] == 1
        assert database.query_one("SELECT 1 FROM schema_migrations WHERE version=2") is None
        names = {r[0] for r in database.query("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "broken" not in names
    finally:
        database.close()


def test_migrate_bad_filename_raises(tmp_path):
    mig_dir = tmp_path / "migrations"
    mig_dir.mkdir()
    (mig_dir / "not_a_migration.sql").write_text("SELECT 1;")
    database = Database(str(tmp_path / "badname.db"))
    try:
        with pytest.raises(RuntimeError):
            database.migrate(mig_dir)
    finally:
        database.close()


def test_nested_tx_raises_and_rolls_back_outer(db):
    with pytest.raises(sqlite3.OperationalError):
        with db.tx() as conn:
            _workout(conn)
            with db.tx():
                pass
    assert db.query_one("SELECT COUNT(*) FROM workout")[0] == 0
    assert db._conn.in_transaction is False
