"""
scripts/build_indexes.py
========================
Adds indexes on subject_id, hadm_id, and stay_id across the relevant tables
in data/mimic.db.

Must be run AFTER scripts/load_data.py.

Per ARCHITECTURE.md Section 2.2 and DATABASE.md Section 2:
- labevents and chartevents are the largest tables and need indexes most.
- All clinical event tables should be indexed on subject_id at minimum.
- hadm_id and stay_id indexes speed up the join queries in timeline.py.

Usage:
    python scripts/build_indexes.py
"""

import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "data" / "mimic.db"

# ---------------------------------------------------------------------------
# Index definitions
# Format: (index_name, table, columns)
# Using IF NOT EXISTS so the script is safe to re-run (idempotent).
# ---------------------------------------------------------------------------
INDEXES = [
    # --- patients ---
    # (subject_id IS the PK; no extra index needed, but no harm)

    # --- admissions ---
    ("idx_admissions_subject_id",  "admissions",     ["subject_id"]),
    ("idx_admissions_hadm_id",     "admissions",     ["hadm_id"]),

    # --- transfers ---
    ("idx_transfers_subject_id",   "transfers",      ["subject_id"]),
    ("idx_transfers_hadm_id",      "transfers",      ["hadm_id"]),

    # --- icustays ---
    ("idx_icustays_subject_id",    "icustays",       ["subject_id"]),
    ("idx_icustays_hadm_id",       "icustays",       ["hadm_id"]),
    ("idx_icustays_stay_id",       "icustays",       ["stay_id"]),

    # --- labevents (LARGE TABLE — most critical indexes) ---
    ("idx_labevents_subject_id",   "labevents",      ["subject_id"]),
    ("idx_labevents_hadm_id",      "labevents",      ["hadm_id"]),
    # Composite: subject_id + hadm_id covers the pattern used in all timeline queries
    ("idx_labevents_subj_hadm",    "labevents",      ["subject_id", "hadm_id"]),
    ("idx_labevents_itemid",       "labevents",      ["itemid"]),
    ("idx_labevents_charttime",    "labevents",      ["charttime"]),

    # --- prescriptions ---
    ("idx_prescriptions_subject_id", "prescriptions", ["subject_id"]),
    ("idx_prescriptions_hadm_id",    "prescriptions", ["hadm_id"]),

    # --- diagnoses_icd ---
    ("idx_diagnoses_subject_id",   "diagnoses_icd",  ["subject_id"]),
    ("idx_diagnoses_hadm_id",      "diagnoses_icd",  ["hadm_id"]),

    # --- procedures_icd ---
    ("idx_procedures_subject_id",  "procedures_icd", ["subject_id"]),
    ("idx_procedures_hadm_id",     "procedures_icd", ["hadm_id"]),

    # --- chartevents (LARGEST TABLE — critical) ---
    ("idx_chartevents_subject_id", "chartevents",    ["subject_id"]),
    ("idx_chartevents_hadm_id",    "chartevents",    ["hadm_id"]),
    ("idx_chartevents_stay_id",    "chartevents",    ["stay_id"]),
    # Composite: subject_id + stay_id + itemid — the exact pattern used for vital queries
    ("idx_chartevents_subj_stay_item", "chartevents", ["subject_id", "stay_id", "itemid"]),
    ("idx_chartevents_charttime",  "chartevents",    ["charttime"]),
    ("idx_chartevents_itemid",     "chartevents",    ["itemid"]),
]


def get_existing_tables(conn: sqlite3.Connection) -> set:
    """Return the set of table names currently in the database."""
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    return {row[0] for row in rows}


def main() -> None:
    if not DB_PATH.exists():
        print(
            f"ERROR: Database not found at {DB_PATH}.\n"
            "Run scripts/load_data.py first."
        )
        sys.exit(1)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    existing_tables = get_existing_tables(conn)
    print(f"Found {len(existing_tables)} tables in database.\n")

    created = 0
    skipped_table = 0
    errors = []

    for index_name, table, columns in INDEXES:
        if table not in existing_tables:
            print(f"  SKIP {index_name} — table '{table}' not found in database")
            skipped_table += 1
            continue

        cols_sql = ", ".join(columns)
        sql = (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table} ({cols_sql})"
        )
        try:
            conn.execute(sql)
            print(f"  OK   {index_name} ON {table}({cols_sql})")
            created += 1
        except sqlite3.Error as exc:
            print(f"  ERR  {index_name}: {exc}")
            errors.append(index_name)

    conn.commit()
    conn.close()

    print(f"\nDone. {created} indexes created/verified.")
    if skipped_table:
        print(f"  {skipped_table} indexes skipped (table missing — run load_data.py first).")
    if errors:
        print(f"  {len(errors)} errors: {errors}")
        sys.exit(1)
    else:
        print("build_indexes.py completed without errors.")


if __name__ == "__main__":
    main()
