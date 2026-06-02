from applykit.db import connect, table_names


def test_connect_creates_all_tables(conn):
    tables = table_names(conn)
    for expected in [
        "applications",
        "calibration_log",
        "crafted_materials",
        "evaluations",
        "feedback",
        "postings_cache",
        "status_history",
    ]:
        assert expected in tables


def test_schema_version_recorded(conn):
    row = conn.execute(
        "SELECT value FROM schema_meta WHERE key = 'schema_version'"
    ).fetchone()
    assert row is not None
    assert row[0] == "1"


def test_foreign_keys_enabled(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_init_is_idempotent(conn):
    # connecting again to the same in-memory handle path shouldn't error;
    # re-running schema on the existing connection is safe.
    from applykit.db import init_schema

    init_schema(conn)
    assert "applications" in table_names(conn)


def test_postings_cache_unique_constraint(conn):
    conn.execute(
        "INSERT INTO postings_cache(company, title, url, url_hash, first_seen) "
        "VALUES('Acme', 'Eng', 'http://x', 'h1', 't')"
    )
    conn.commit()
    import sqlite3
    import pytest

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO postings_cache(company, title, url, url_hash, first_seen) "
            "VALUES('Acme', 'Eng', 'http://x', 'h1', 't')"
        )
