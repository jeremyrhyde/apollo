import sqlite3

import pytest

from core.state import Database

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
    assert db.migrate() == 1
    assert db.query_one("SELECT COUNT(*) FROM schema_migrations")[0] == 1


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
