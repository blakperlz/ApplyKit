"""SQLite connection manager and schema — the data contract.

Per ADR-001 Tension 3: one ``applykit.db`` file, seven tables. This is the
shared surface between the Cowork layer and the CLI layer. Both read and write
these exact tables, so the schema here is the source of truth.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

# Seven tables (ADR-001 Tension 3). JSON columns store serialised dimension
# score lists and weight maps.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS postings_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL,
    url_hash    TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    UNIQUE(company, url_hash)
);

CREATE TABLE IF NOT EXISTS applications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    company     TEXT NOT NULL,
    role        TEXT NOT NULL,
    url         TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evaluations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id            INTEGER,
    company           TEXT NOT NULL,
    role              TEXT NOT NULL,
    overall_score     REAL NOT NULL,
    grade             TEXT NOT NULL,
    dimension_scores  TEXT NOT NULL,   -- JSON
    recommendation    TEXT NOT NULL DEFAULT '',
    source            TEXT NOT NULL DEFAULT '',
    raw_jd            TEXT NOT NULL DEFAULT '',
    evaluated_at      TEXT NOT NULL,
    FOREIGN KEY(app_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS status_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id      INTEGER NOT NULL,
    from_status TEXT,
    to_status   TEXT NOT NULL,
    note        TEXT NOT NULL DEFAULT '',
    timestamp   TEXT NOT NULL,
    FOREIGN KEY(app_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS feedback (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id              INTEGER NOT NULL,
    verdict             TEXT NOT NULL,
    reason              TEXT NOT NULL DEFAULT '',
    dimension_snapshot  TEXT NOT NULL DEFAULT '[]',  -- JSON
    timestamp           TEXT NOT NULL,
    FOREIGN KEY(app_id) REFERENCES applications(id)
);

CREATE TABLE IF NOT EXISTS calibration_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    old_weights     TEXT NOT NULL,    -- JSON
    new_weights     TEXT NOT NULL,    -- JSON
    trigger_pattern TEXT NOT NULL DEFAULT '',
    accepted        INTEGER NOT NULL DEFAULT 0,
    timestamp       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crafted_materials (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id            INTEGER NOT NULL,
    resume_path       TEXT NOT NULL DEFAULT '',
    cover_letter_path TEXT NOT NULL DEFAULT '',
    crafted_at        TEXT NOT NULL,
    FOREIGN KEY(app_id) REFERENCES applications(id)
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    """Create all tables if absent and stamp the schema version."""
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO schema_meta(key, value) VALUES('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()


def connect(path: str | Path = "applykit.db") -> sqlite3.Connection:
    """Open (creating if needed) the database and ensure the schema exists.

    Returns a connection with ``row_factory`` set to :class:`sqlite3.Row` and
    foreign keys enabled. ``:memory:`` is supported for tests.
    """
    p = str(path)
    if p != ":memory:":
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    init_schema(conn)
    return conn


@contextmanager
def session(path: str | Path = "applykit.db") -> Iterator[sqlite3.Connection]:
    """Context manager that commits on success and always closes the connection."""
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def table_names(conn: sqlite3.Connection) -> list[str]:
    """Return user table names, sorted — handy for tests and diagnostics."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return sorted(r[0] for r in rows)
