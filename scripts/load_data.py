"""
scripts/load_data.py
====================
Loads the 13 MIMIC-IV Demo tables listed in DATABASE.md Section 2 into
data/mimic.db (SQLite).

Usage:
    python scripts/load_data.py

Pre-condition:
    data/raw/hosp/ and data/raw/icu/ CSV (or CSV.GZ) folders must be present.

Loading rules (DATABASE.md Section 5):
1. Preserve leading zeros — code-like fields (icd_code, drug, etc.) loaded as TEXT.
2. Parse all *time / *date columns as proper datetime strings so sorting works.
3. Do NOT drop null rows — nulls are meaningful.
4. Print row counts per table after loading.
5. Idempotent — drop and recreate each table on every run.
"""

import sqlite3
import sys
import os
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
HOSP_DIR = RAW_DIR / "hosp"
ICU_DIR = RAW_DIR / "icu"
DB_PATH = PROJECT_ROOT / "data" / "mimic.db"


# ---------------------------------------------------------------------------
# Table definitions
# Each entry:
#   table_name  : target SQLite table name
#   source_dir  : HOSP_DIR or ICU_DIR
#   filename    : CSV filename (without compression extension)
#   dtype_overrides : columns that must be read as str (preserve leading zeros,
#                     prevent pandas from casting to int/float)
#   datetime_cols   : columns to parse as datetimes
# ---------------------------------------------------------------------------
TABLE_SPECS = [
    {
        "table": "patients",
        "dir": HOSP_DIR,
        "file": "patients",
        "dtypes": {},
        "datetimes": ["dod"],
    },
    {
        "table": "admissions",
        "dir": HOSP_DIR,
        "file": "admissions",
        "dtypes": {},
        "datetimes": ["admittime", "dischtime", "deathtime"],
    },
    {
        "table": "transfers",
        "dir": HOSP_DIR,
        "file": "transfers",
        "dtypes": {},
        "datetimes": ["intime", "outtime"],
    },
    {
        "table": "icustays",
        "dir": ICU_DIR,
        "file": "icustays",
        "dtypes": {},
        "datetimes": ["intime", "outtime"],
    },
    {
        "table": "labevents",
        "dir": HOSP_DIR,
        "file": "labevents",
        "dtypes": {},
        "datetimes": ["charttime", "storetime"],
    },
    {
        "table": "d_labitems",
        "dir": HOSP_DIR,
        "file": "d_labitems",
        "dtypes": {},
        "datetimes": [],
    },
    {
        "table": "prescriptions",
        "dir": HOSP_DIR,
        "file": "prescriptions",
        # drug field: keep as TEXT even if it looks numeric
        "dtypes": {"drug": str, "dose_val_rx": str, "dose_unit_rx": str,
                   "route": str, "drug_type": str},
        "datetimes": ["starttime", "stoptime"],
    },
    {
        "table": "diagnoses_icd",
        "dir": HOSP_DIR,
        "file": "diagnoses_icd",
        # icd_code MUST be TEXT — leading zeros matter (e.g. "0011")
        "dtypes": {"icd_code": str},
        "datetimes": [],
    },
    {
        "table": "d_icd_diagnoses",
        "dir": HOSP_DIR,
        "file": "d_icd_diagnoses",
        "dtypes": {"icd_code": str},
        "datetimes": [],
    },
    {
        "table": "procedures_icd",
        "dir": HOSP_DIR,
        "file": "procedures_icd",
        "dtypes": {"icd_code": str},
        "datetimes": ["chartdate"],
    },
    {
        "table": "d_icd_procedures",
        "dir": HOSP_DIR,
        "file": "d_icd_procedures",
        "dtypes": {"icd_code": str},
        "datetimes": [],
    },
    {
        "table": "chartevents",
        "dir": ICU_DIR,
        "file": "chartevents",
        "dtypes": {},
        "datetimes": ["charttime", "storetime"],
    },
    {
        "table": "d_items",
        "dir": ICU_DIR,
        "file": "d_items",
        "dtypes": {},
        "datetimes": [],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def find_csv(directory: Path, stem: str) -> Path:
    """
    Return the path to a CSV file (plain or gzip-compressed).
    Tries: <stem>.csv, <stem>.csv.gz in that order.
    Raises FileNotFoundError with a helpful message if neither exists.
    """
    for suffix in (".csv", ".csv.gz"):
        candidate = directory / (stem + suffix)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Could not find '{stem}.csv' or '{stem}.csv.gz' in {directory}.\n"
        f"Place the MIMIC-IV Demo hosp/ and icu/ folders inside {RAW_DIR} "
        f"before running this script."
    )


def load_table(conn: sqlite3.Connection, spec: dict) -> int:
    """
    Load one MIMIC-IV CSV into SQLite.

    Steps:
      1. Locate the CSV (plain or gzip).
      2. Read with pandas, using dtype overrides to preserve string fields.
      3. Parse datetime columns into ISO-8601 strings (SQLite stores them as TEXT).
         Nulls are left as NaT → pandas writes them as None → SQLite NULL.
      4. Drop the target table if it exists (idempotency).
      5. Write the DataFrame to SQLite.
      6. Return the row count.
    """
    table_name = spec["table"]
    csv_path = find_csv(spec["dir"], spec["file"])

    # Step 2: read CSV, keeping string dtypes for code fields
    df = pd.read_csv(
        csv_path,
        dtype=spec["dtypes"],
        low_memory=False,      # avoid mixed-type inference warnings on large files
    )

    # Step 3: parse datetime columns
    for col in spec["datetimes"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
            # Convert to ISO-8601 string for SQLite; NaT → None (NULL)
            df[col] = df[col].apply(
                lambda ts: ts.isoformat() if pd.notna(ts) else None
            )

    # Step 4 + 5: write to SQLite (replace = drop + recreate, idempotent)
    df.to_sql(table_name, conn, if_exists="replace", index=False)

    return len(df)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # Validate that the raw data directories exist before doing anything
    missing = []
    for d in (HOSP_DIR, ICU_DIR):
        if not d.is_dir():
            missing.append(str(d))
    if missing:
        print("ERROR: The following expected data directories are missing:")
        for m in missing:
            print(f"  {m}")
        print(
            "\nPlace the MIMIC-IV Demo v2.2 hosp/ and icu/ CSV folders inside:\n"
            f"  {RAW_DIR}\n"
            "Then re-run this script."
        )
        sys.exit(1)

    # Ensure data/ directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)

    # Increase cache and WAL mode for faster bulk inserts
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64 MB cache

    print(f"\nLoading {len(TABLE_SPECS)} tables from {RAW_DIR} ...\n")

    total_rows = 0
    failed = []

    for spec in TABLE_SPECS:
        table_name = spec["table"]
        try:
            row_count = load_table(conn, spec)
            total_rows += row_count
            print(f"  {table_name}: {row_count:,} rows loaded")
        except FileNotFoundError as exc:
            print(f"  {table_name}: SKIPPED — {exc}")
            failed.append(table_name)
        except Exception as exc:
            print(f"  {table_name}: ERROR — {exc}")
            failed.append(table_name)

    conn.commit()
    conn.close()

    print(f"\nDone. Total rows across all tables: {total_rows:,}")
    if failed:
        print(f"\nWARNING: The following tables failed to load: {failed}")
        sys.exit(1)
    else:
        print("All 13 tables loaded successfully.")


if __name__ == "__main__":
    main()
