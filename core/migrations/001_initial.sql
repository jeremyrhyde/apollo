-- Apollo initial schema. Forward-only: never edit after it has run anywhere;
-- add 002_*.sql instead. Timestamps are UTC ISO-8601; local_date is
-- YYYY-MM-DD from services/clock.py; measurements are SI (kg, m, s).
-- Names are snapshotted at log time so history survives catalog edits.

CREATE TABLE workout (
  id          INTEGER PRIMARY KEY,
  started_at  TEXT NOT NULL,
  ended_at    TEXT,                          -- NULL = open
  local_date  TEXT NOT NULL,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
-- At most one open workout: the indexed expression is 1 for every open row.
CREATE UNIQUE INDEX ux_workout_one_open ON workout(ended_at IS NULL) WHERE ended_at IS NULL;
CREATE INDEX ix_workout_date ON workout(local_date);

CREATE TABLE workout_exercise (
  id            INTEGER PRIMARY KEY,
  workout_id    INTEGER NOT NULL REFERENCES workout(id) ON DELETE CASCADE,
  position      INTEGER NOT NULL,
  exercise_key  TEXT NOT NULL,
  exercise_name TEXT NOT NULL,                -- snapshot
  metric_type   TEXT NOT NULL,                -- snapshot
  metric_fields TEXT NOT NULL,                -- snapshot, e.g. 'weight,reps'
  planned       INTEGER NOT NULL DEFAULT 0,   -- 1 = added by a plan, not the user
  notes         TEXT
);
CREATE INDEX ix_we_workout ON workout_exercise(workout_id);
CREATE INDEX ix_we_key ON workout_exercise(exercise_key);

CREATE TABLE workout_exercise_group (
  workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercise(id) ON DELETE CASCADE,
  muscle_group        TEXT NOT NULL,          -- snapshot
  PRIMARY KEY (workout_exercise_id, muscle_group)
);
CREATE INDEX ix_weg_group ON workout_exercise_group(muscle_group);

CREATE TABLE workout_set (
  id                  INTEGER PRIMARY KEY,
  workout_exercise_id INTEGER NOT NULL REFERENCES workout_exercise(id) ON DELETE CASCADE,
  position            INTEGER NOT NULL,
  done                INTEGER NOT NULL DEFAULT 0,
  weight_kg           REAL,                   -- NULL = not applicable
  reps                INTEGER,
  distance_m          REAL,
  duration_s          INTEGER,
  updated_at          TEXT NOT NULL
);
CREATE INDEX ix_ws_exercise ON workout_set(workout_exercise_id);

CREATE TABLE selfcare_session (
  id           INTEGER PRIMARY KEY,
  category_key TEXT NOT NULL,
  performed_at TEXT NOT NULL,
  local_date   TEXT NOT NULL,
  notes        TEXT,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX ix_ss_cat_date ON selfcare_session(category_key, local_date);
CREATE INDEX ix_ss_date ON selfcare_session(local_date);

CREATE TABLE selfcare_session_type (
  session_id INTEGER NOT NULL REFERENCES selfcare_session(id) ON DELETE CASCADE,
  type_key   TEXT NOT NULL,
  type_name  TEXT NOT NULL,                   -- snapshot
  PRIMARY KEY (session_id, type_key)
);
CREATE INDEX ix_sst_type ON selfcare_session_type(type_key);

CREATE TABLE preferences (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
