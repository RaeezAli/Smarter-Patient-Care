"""
app/db.py
=========
SQLite connection factory for the Smarter Patient Care app.

Per ARCHITECTURE.md Section 2.3:
- This is the ONLY place in the codebase that calls sqlite3.connect().
- All other modules (timeline.py, queries.py, etc.) must call get_db_connection()
  and never open their own raw connection.
- row_factory = sqlite3.Row is set so results can be accessed by column name
  throughout timeline.py and citations.py.
"""

import sqlite3
from pathlib import Path

# Database path, relative to this file's location (app/ -> project root -> data/)
_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "mimic.db"


def get_db_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection to data/mimic.db.

    The connection has row_factory = sqlite3.Row set, so all query results
    support column-name access (e.g. row["subject_id"]) in addition to
    positional access.

    The caller is responsible for closing the connection when done.
    Use a try/finally block or a context manager in the calling code.

    Raises:
        sqlite3.OperationalError: if the database file cannot be opened
            (e.g., load_data.py has not been run yet).
    """
    if not _DB_PATH.exists():
        raise sqlite3.OperationalError(
            f"Database not found at {_DB_PATH}. "
            "Run scripts/load_data.py (and scripts/build_indexes.py) first."
        )

    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    # Enforce foreign key constraints at the connection level
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
