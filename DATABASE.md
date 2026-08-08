# DATABASE.md — Data Model & Schema Reference

## 1. Source

MIMIC-IV Clinical Database Demo v2.2 (PhysioNet). Distributed as compressed relational CSVs, organized into `hosp/` (hospital-wide data) and `icu/` (ICU-specific data) modules. This project loads a subset of tables into a single local SQLite database at `data/mimic.db`.

Reference: https://physionet.org/content/mimic-iv-demo/2.2/
Schema reference: https://mimic.mit.edu/docs/IV/about/schema-overview.html

**Deidentification note:** All dates are shifted per-patient by a random offset. Do not infer real calendar dates, seasonality, or cross-patient chronology from timestamps. Relative time *within* a single patient's record (e.g., "3 days after admission") is valid; absolute dates are not clinically meaningful.

## 2. Tables Used in This Project

Only the tables below are loaded. Do not load or reference other MIMIC-IV tables unless a feature explicitly requires them — smaller scope means less to test and audit in 2 days.

### 2.1 `patients` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | Primary key. Unique per patient. |
| gender | TEXT | 'M' / 'F' |
| anchor_age | INTEGER | Patient's age at anchor_year (deidentified age reference point) |
| anchor_year | INTEGER | Deidentified reference year, not a real calendar year |
| anchor_year_group | TEXT | e.g. "2011 - 2013" (a range, for further deidentification) |
| dod | DATETIME (nullable) | Date of death, if applicable and known |

### 2.2 `admissions` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | Primary key for the admission (hospital admission ID) |
| admittime | DATETIME | |
| dischtime | DATETIME | |
| deathtime | DATETIME (nullable) | |
| admission_type | TEXT | e.g. EW EMER., ELECTIVE, URGENT |
| admission_location | TEXT | |
| discharge_location | TEXT | |
| insurance | TEXT | |
| language | TEXT | |
| marital_status | TEXT | |
| race | TEXT | |
| hospital_expire_flag | INTEGER | 1 if patient died during this admission |

### 2.3 `transfers` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER (nullable) | FK → admissions |
| transfer_id | INTEGER | Primary key |
| eventtype | TEXT | 'admit', 'transfer', 'discharge' |
| careunit | TEXT (nullable) | Ward/unit name, e.g. "Medical Intensive Care Unit (MICU)" |
| intime | DATETIME | |
| outtime | DATETIME (nullable) | |

### 2.4 `icustays` (icu module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | FK → admissions |
| stay_id | INTEGER | Primary key |
| first_careunit | TEXT | |
| last_careunit | TEXT | |
| intime | DATETIME | |
| outtime | DATETIME | |
| los | REAL | Length of stay, in days |

### 2.5 `labevents` (hosp module) — LARGE TABLE, index this
| Column | Type | Notes |
|---|---|---|
| labevent_id | INTEGER | Primary key |
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER (nullable) | FK → admissions |
| specimen_id | INTEGER | |
| itemid | INTEGER | FK → d_labitems |
| charttime | DATETIME | |
| storetime | DATETIME (nullable) | |
| value | TEXT (nullable) | Raw value, may be non-numeric (e.g., "POSITIVE") |
| valuenum | REAL (nullable) | Numeric value, if applicable |
| valueuom | TEXT (nullable) | Unit of measure |
| ref_range_lower | REAL (nullable) | |
| ref_range_upper | REAL (nullable) | |
| flag | TEXT (nullable) | e.g. "abnormal" |
| priority | TEXT (nullable) | |
| comments | TEXT (nullable) | Free text — DO NOT surface this as if clinician-authored prose; treat as raw supplementary field only, per brief's restriction on presenting structured data as notes |

### 2.6 `d_labitems` (hosp module) — dictionary table
| Column | Type | Notes |
|---|---|---|
| itemid | INTEGER | Primary key |
| label | TEXT | Human-readable lab name, e.g. "Hemoglobin" |
| fluid | TEXT | e.g. "Blood" |
| category | TEXT | e.g. "Hematology" |

### 2.7 `prescriptions` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | FK → admissions |
| pharmacy_id | INTEGER | |
| starttime | DATETIME | |
| stoptime | DATETIME (nullable) | |
| drug_type | TEXT | |
| drug | TEXT | Drug name |
| dose_val_rx | TEXT | |
| dose_unit_rx | TEXT | |
| route | TEXT | e.g. "PO", "IV" |

*Note: prescriptions has no single-column primary key in the raw dataset. Use `(subject_id, hadm_id, pharmacy_id, starttime, drug)` as a composite row identifier for citation purposes — see Section 4.*

### 2.8 `diagnoses_icd` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | FK → admissions |
| seq_num | INTEGER | Priority order of diagnosis |
| icd_code | TEXT | FK → d_icd_diagnoses (composite with icd_version) |
| icd_version | INTEGER | 9 or 10 |

### 2.9 `d_icd_diagnoses` (hosp module) — dictionary table
| Column | Type | Notes |
|---|---|---|
| icd_code | TEXT | Composite PK with icd_version |
| icd_version | INTEGER | |
| long_title | TEXT | Human-readable diagnosis description |

### 2.10 `procedures_icd` (hosp module)
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | FK → admissions |
| seq_num | INTEGER | |
| chartdate | DATE | |
| icd_code | TEXT | FK → d_icd_procedures |
| icd_version | INTEGER | |

### 2.11 `d_icd_procedures` (hosp module) — dictionary table
| Column | Type | Notes |
|---|---|---|
| icd_code | TEXT | Composite PK with icd_version |
| icd_version | INTEGER | |
| long_title | TEXT | Human-readable procedure description |

### 2.12 `chartevents` (icu module) — LARGEST TABLE, index heavily, query narrowly
| Column | Type | Notes |
|---|---|---|
| subject_id | INTEGER | FK → patients |
| hadm_id | INTEGER | FK → admissions |
| stay_id | INTEGER | FK → icustays |
| charttime | DATETIME | |
| storetime | DATETIME (nullable) | |
| itemid | INTEGER | FK → d_items |
| value | TEXT (nullable) | |
| valuenum | REAL (nullable) | |
| valueuom | TEXT (nullable) | |
| warning | INTEGER (nullable) | 1 if flagged as a warning value |

**Important:** `chartevents` contains thousands of distinct `itemid` values (all monitored ICU parameters). For this project, filter to a curated whitelist of key vitals only (heart rate, blood pressure, respiratory rate, temperature, SpO2, GCS) — do not attempt to display every chartevent, or the timeline becomes unreadable and query latency suffers. Maintain this whitelist as a constant list of `itemid`s in `app/timeline.py`, sourced by looking up labels in `d_items`.

### 2.13 `d_items` (icu module) — dictionary table
| Column | Type | Notes |
|---|---|---|
| itemid | INTEGER | Primary key |
| label | TEXT | Human-readable name |
| abbreviation | TEXT (nullable) | |
| linksto | TEXT | Which table this itemid applies to (e.g. "chartevents") |
| category | TEXT | |
| unitname | TEXT (nullable) | |

## 3. Key Relationships (Join Map)

```
patients (subject_id)
   └── admissions (subject_id, hadm_id)
          ├── transfers (subject_id, hadm_id)
          ├── icustays (subject_id, hadm_id, stay_id)
          │      └── chartevents (subject_id, hadm_id, stay_id) ──▶ d_items (itemid)
          ├── labevents (subject_id, hadm_id) ──▶ d_labitems (itemid)
          ├── prescriptions (subject_id, hadm_id)
          ├── diagnoses_icd (subject_id, hadm_id) ──▶ d_icd_diagnoses (icd_code, icd_version)
          └── procedures_icd (subject_id, hadm_id) ──▶ d_icd_procedures (icd_code, icd_version)
```

**Rule for the whole codebase:** every query that touches a clinical event table must join through `subject_id` (and `hadm_id` where available) — never query `labevents` or `chartevents` for a patient without also filtering by `subject_id`. These tables are shared across all 100 patients; an unfiltered or mis-filtered query will silently leak another patient's data into the timeline. This is the single most important correctness rule in this codebase.

## 4. Citation Row Identifiers

Every table used for citations needs a stable identifier:

| Table | Row identifier used for citations |
|---|---|
| admissions | `hadm_id` |
| transfers | `transfer_id` |
| icustays | `stay_id` |
| labevents | `labevent_id` |
| prescriptions | `pharmacy_id` + `starttime` (composite, no single PK exists) |
| diagnoses_icd | `hadm_id` + `seq_num` (composite) |
| procedures_icd | `hadm_id` + `seq_num` (composite) |
| chartevents | `subject_id` + `charttime` + `itemid` (composite, no single PK exists) |

## 5. Loading Rules (for `scripts/load_data.py`)

1. Preserve leading zeros and exact string formatting in any code-like field (`icd_code`, `drug`, etc.) — load as TEXT, never as INTEGER, even if it looks numeric.
2. Parse all `*time` and `*date` columns as proper datetime objects on load, not left as raw strings, so sorting works correctly in `timeline.py`.
3. Do not drop rows with null values — nulls are meaningful (e.g., `dischtime` null means still admitted; `outtime` null in `transfers` means still in that unit) and must be handled explicitly downstream, not silently filtered out at load time.
4. After loading, print row counts per table to the console as a sanity check (e.g., `admissions: 275 rows loaded`).
5. This script must be idempotent — running it twice should produce the same database, not duplicate rows. Drop and recreate each table at the start of the script.

## 6. Evaluation Split Note

This track does not involve model training, so there is no train/test split requirement in the strict sense. However, when building the evaluation report (`docs/evaluation_report.md`), sample verification facts from at least 3 different patients, not just the "hero patient" used for development — this avoids over-fitting your manual QA process to the one patient you've stared at all weekend.
