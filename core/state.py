"""The one SQLite connection: transactions and forward-only migrations.

stdlib sqlite3 in autocommit mode; writes go through `tx()` (BEGIN IMMEDIATE …
COMMIT/ROLLBACK), reads through `read()`/`query()`. A re-entrant lock
serialises access because FastAPI runs sync handlers on a threadpool.

`tx()` must not be nested — services open one transaction per public method
and pass the connection to their private helpers.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_NAME_RE = re.compile(r"^(\d{3})_([a-z0-9_]+)\.sql$")


class Database:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        for pragma in (
            "PRAGMA journal_mode=WAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA busy_timeout=5000",
        ):
            self._conn.execute(pragma)

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield self._conn
            except BaseException:
                # sqlite can auto-rollback on its own (SQLITE_FULL, an
                # interrupt) before we get here; only issue ROLLBACK if a
                # transaction is still open, or we'd mask the real error
                # with "cannot rollback - no transaction is active".
                if self._conn.in_transaction:
                    self._conn.execute("ROLLBACK")
                raise
            else:
                try:
                    self._conn.execute("COMMIT")
                except BaseException:
                    # If COMMIT itself fails, roll back so the long-lived
                    # connection isn't left stuck inside a transaction.
                    if self._conn.in_transaction:
                        self._conn.execute("ROLLBACK")
                    raise

    @contextmanager
    def read(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            yield self._conn

    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    def query_one(self, sql: str, params: tuple | list = ()) -> sqlite3.Row | None:
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def migrate(self, migrations_dir: Path = MIGRATIONS_DIR) -> int:
        """Apply unapplied NNN_name.sql files in order; return the schema version.

        Migration files must not contain BEGIN/COMMIT/ROLLBACK — each file is
        wrapped in its own transaction here, and a failure leaves no partial
        schema and no row in schema_migrations for it. `PRAGMA foreign_keys`
        has no effect inside a migration; it's a per-connection setting
        applied once at startup, not something a migration script can toggle.
        """
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL)"
            )
            applied = {r[0] for r in self._conn.execute("SELECT version FROM schema_migrations")}
            for path in sorted(migrations_dir.glob("*.sql")):
                match = _NAME_RE.match(path.name)
                if match is None:
                    raise RuntimeError(f"bad migration filename: {path.name}")
                version, name = int(match.group(1)), match.group(2)
                if version in applied:
                    continue
                now = datetime.now(UTC).isoformat(timespec="seconds")
                script = (
                    "BEGIN;\n"
                    + path.read_text(encoding="utf-8")
                    + f"\nINSERT INTO schema_migrations (version, name, applied_at) "
                    f"VALUES ({version}, '{name}', '{now}');\nCOMMIT;"
                )
                try:
                    self._conn.executescript(script)
                except sqlite3.Error:
                    if self._conn.in_transaction:
                        self._conn.execute("ROLLBACK")
                    raise
            row = self._conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
            return int(row[0] or 0)

    def close(self) -> None:
        with self._lock:
            self._conn.close()
