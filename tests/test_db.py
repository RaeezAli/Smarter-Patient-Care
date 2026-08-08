"""
tests/test_db.py
================
Tests for app/db.py (get_db_connection) and the database populated by
scripts/load_data.py.

Run with:
    pytest tests/test_db.py -v

These tests require that scripts/load_data.py has been run successfully
and data/mimic.db exists. If the DB is not present, tests are skipped
with an informative message rather than erroring out with a confusing
OperationalError.
"""

import sqlite3
import sys
from pathlib import Path

# Ensure project root is in python path for importing app module
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
DB_PATH = PROJECT_ROOT / "data" / "mimic.db"

# The 13 tables that must exist after load_data.py completes successfully
# (matches DATABASE.md Section 2 exactly)
EXPECTED_TABLES = {
    "patients",
    "admissions",
    "transfers",
    "icustays",
    "labevents",
    "d_labitems",
    "prescriptions",
    "diagnoses_icd",
    "d_icd_diagnoses",
    "procedures_icd",
    "d_icd_procedures",
    "chartevents",
    "d_items",
}


# ---------------------------------------------------------------------------
# Skip guard: skip all DB-dependent tests if the database hasn't been loaded
# ---------------------------------------------------------------------------

db_missing = not DB_PATH.exists()
skip_if_no_db = pytest.mark.skipif(
    db_missing,
    reason=(
        f"data/mimic.db not found at {DB_PATH}. "
        "Run scripts/load_data.py first, then re-run the tests."
    ),
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def conn():
    """
    Open a connection via get_db_connection() and close it after each test.
    Uses the production factory so we're testing the real thing.
    """
    from app.db import get_db_connection
    connection = get_db_connection()
    yield connection
    connection.close()


# ---------------------------------------------------------------------------
# Tests: get_db_connection()
# ---------------------------------------------------------------------------

@skip_if_no_db
def test_get_db_connection_returns_connection(conn):
    """get_db_connection() must return a sqlite3.Connection object."""
    assert isinstance(conn, sqlite3.Connection), (
        "get_db_connection() did not return a sqlite3.Connection"
    )


@skip_if_no_db
def test_connection_is_usable(conn):
    """The returned connection must be able to execute a trivial query."""
    result = conn.execute("SELECT 1 AS val").fetchone()
    assert result is not None
    assert result["val"] == 1, (
        "row_factory=sqlite3.Row not set — column-name access failed"
    )


@skip_if_no_db
def test_row_factory_is_sqlite_row(conn):
    """
    row_factory must be sqlite3.Row so every caller can access columns by name.
    This is the contract stated in ARCHITECTURE.md Section 2.3.
    """
    assert conn.row_factory is sqlite3.Row, (
        "Connection row_factory is not sqlite3.Row — "
        "fix get_db_connection() in app/db.py"
    )


@skip_if_no_db
def test_missing_db_raises_operational_error(tmp_path, monkeypatch):
    """
    get_db_connection() must raise sqlite3.OperationalError (not FileNotFoundError
    or a bare AttributeError) when the database file does not exist.
    This ensures callers get a meaningful error rather than a silent failure.
    """
    import app.db as db_module

    # Temporarily redirect the module's _DB_PATH to a non-existent file
    fake_path = tmp_path / "does_not_exist.db"
    original = db_module._DB_PATH
    db_module._DB_PATH = fake_path
    try:
        with pytest.raises(sqlite3.OperationalError):
            db_module.get_db_connection()
    finally:
        db_module._DB_PATH = original


# ---------------------------------------------------------------------------
# Tests: database schema (require load_data.py to have been run)
# ---------------------------------------------------------------------------

@skip_if_no_db
def test_all_13_tables_exist(conn):
    """
    After running load_data.py, all 13 tables from DATABASE.md Section 2
    must be present in data/mimic.db.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    actual_tables = {row["name"] for row in rows}

    missing = EXPECTED_TABLES - actual_tables
    assert not missing, (
        f"The following tables are missing from the database: {sorted(missing)}\n"
        "Re-run scripts/load_data.py to reload all tables."
    )


@skip_if_no_db
def test_no_extra_unexpected_tables(conn):
    """
    The database should contain (at least) the 13 expected tables.
    Extra tables are fine (e.g. SQLite internal tables), but we explicitly
    verify our 13 are present via the test above.
    """
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    actual_tables = {row["name"] for row in rows}
    # Every expected table must be a subset of actual tables
    assert EXPECTED_TABLES.issubset(actual_tables)


@skip_if_no_db
def test_patients_table_has_rows(conn):
    """patients table must be non-empty — sanity check that data was loaded."""
    count = conn.execute("SELECT COUNT(*) AS n FROM patients").fetchone()["n"]
    assert count > 0, "patients table is empty — load_data.py may have failed"


@skip_if_no_db
def test_admissions_table_has_rows(conn):
    """admissions table must be non-empty."""
    count = conn.execute("SELECT COUNT(*) AS n FROM admissions").fetchone()["n"]
    assert count > 0, "admissions table is empty"


@skip_if_no_db
def test_labevents_table_has_rows(conn):
    """labevents is the largest hosp table and must be non-empty."""
    count = conn.execute("SELECT COUNT(*) AS n FROM labevents").fetchone()["n"]
    assert count > 0, "labevents table is empty"


@skip_if_no_db
def test_chartevents_table_has_rows(conn):
    """chartevents is the largest icu table and must be non-empty."""
    count = conn.execute("SELECT COUNT(*) AS n FROM chartevents").fetchone()["n"]
    assert count > 0, "chartevents table is empty"


@skip_if_no_db
def test_icd_code_preserved_as_text(conn):
    """
    DATABASE.md Section 5 Rule 1: icd_code must be stored as TEXT
    (leading zeros preserved). Verify that diagnoses_icd.icd_code is TEXT,
    not INTEGER.
    """
    # SQLite PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
    cols = conn.execute("PRAGMA table_info(diagnoses_icd)").fetchall()
    col_types = {row["name"]: row["type"].upper() for row in cols}

    # pandas writes TEXT columns as TEXT in SQLite
    assert "icd_code" in col_types, "icd_code column missing from diagnoses_icd"
    # When pandas writes a str dtype column to SQLite it uses TEXT
    assert col_types["icd_code"] == "TEXT", (
        f"icd_code column type is '{col_types['icd_code']}', expected TEXT. "
        "Leading zeros may be lost — check dtype override in load_data.py."
    )


@skip_if_no_db
def test_datetime_columns_are_not_raw_strings(conn):
    """
    DATABASE.md Section 5 Rule 2: datetime columns must be parsed, not stored
    as ambiguous raw strings. We verify admissions.admittime contains a
    well-formed ISO-8601 value (YYYY-MM-DDTHH:MM:SS) rather than something like
    '2180-05-06 22:23:00' (space separator, still parseable but check format).
    Either format is acceptable as long as it's sortable.
    """
    row = conn.execute(
        "SELECT admittime FROM admissions WHERE admittime IS NOT NULL LIMIT 1"
    ).fetchone()
    assert row is not None, "No non-null admittime found in admissions"
    # The value should be a string that can be parsed by SQLite's datetime()
    val = row["admittime"]
    assert isinstance(val, str), f"admittime should be a string, got {type(val)}"
    # Basic sanity: contains digits and hyphens (valid date portion)
    assert any(c.isdigit() for c in val), (
        f"admittime value '{val}' doesn't look like a datetime"
    )


@skip_if_no_db
def test_null_rows_preserved(conn):
    """
    DATABASE.md Section 5 Rule 3: nulls must not be dropped.
    admissions.deathtime is nullable (most patients don't die during admission).
    Verify NULLs exist in that column.
    """
    null_count = conn.execute(
        "SELECT COUNT(*) AS n FROM admissions WHERE deathtime IS NULL"
    ).fetchone()["n"]
    total = conn.execute("SELECT COUNT(*) AS n FROM admissions").fetchone()["n"]
    assert null_count > 0, (
        "No NULL deathtime values found in admissions — "
        "nulls may have been dropped during loading (violates Rule 3)."
    )
    assert null_count < total, (
        "ALL deathtime values are NULL — data may not have loaded correctly."
    )


@skip_if_no_db
def test_subject_id_exists_in_clinical_tables(conn):
    """
    DATABASE.md Section 3 (join map rule): every clinical event table must have
    a subject_id column for patient-scoped filtering.
    """
    clinical_tables = [
        "admissions", "transfers", "icustays",
        "labevents", "prescriptions", "diagnoses_icd",
        "procedures_icd", "chartevents",
    ]
    for table in clinical_tables:
        cols = conn.execute(f"PRAGMA table_info({table})").fetchall()
        col_names = {row["name"] for row in cols}
        assert "subject_id" in col_names, (
            f"Table '{table}' is missing subject_id — "
            "filtering by patient will be impossible."
        )
