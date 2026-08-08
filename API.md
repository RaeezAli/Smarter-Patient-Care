# API.md — Flask Route Specification

This is a server-rendered Flask app, not a JSON API — routes return rendered HTML (Jinja2 templates), not JSON, except where noted. Kept minimal and predictable on purpose.

## 1. Route Summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Home page — patient picker |
| GET | `/patient/<int:subject_id>` | Timeline view for one patient |
| GET | `/patient/<int:subject_id>/ask` | Q&A panel for one patient (shows question list) |
| POST | `/patient/<int:subject_id>/ask` | Submit a question, return answer + citations |
| GET | `/about` | Safety statement, limitations, methodology (static page) |
| GET | `/health` | Simple JSON health check — `{"status": "ok"}` (for local debugging only) |

## 2. Route Details

### 2.1 `GET /`
**Purpose:** Landing page. Lists all 100 available `subject_id`s in a searchable/sortable dropdown or table, pulled from the `patients` table (plus basic non-identifying context like gender and age, from `patients`, to help the user pick a patient without needing to know IDs by memory).

**Renders:** `templates/index.html`

**Data needed:** `SELECT subject_id, gender, anchor_age FROM patients ORDER BY subject_id;`

---

### 2.2 `GET /patient/<int:subject_id>`
**Purpose:** Main timeline view.

**Behavior:**
1. Call `timeline.get_patient_timeline(subject_id)`.
2. If `subject_id` does not exist in `patients`, render a clean "Patient not found" state (HTTP 404), not a stack trace.
3. If it exists, render the full timeline: admissions, transfers, labs, prescriptions, diagnoses, procedures, and whitelisted ICU chart events, all time-sorted, each with a citation tag.
4. Render the `undated_events` section separately, below the main timeline, clearly labeled.

**Renders:** `templates/timeline.html`

**Template context:**
```python
{
  "subject_id": int,
  "patient_summary": {"gender": str, "anchor_age": int},
  "timeline_events": list[TimelineEvent],
  "undated_events": list[TimelineEvent],
}
```

---

### 2.3 `GET /patient/<int:subject_id>/ask`
**Purpose:** Shows the fixed list of supported questions for this patient (see Section 3), as buttons/links — not a free-text input.

**Renders:** `templates/qa.html` (initial state, no answer yet)

---

### 2.4 `POST /patient/<int:subject_id>/ask`
**Purpose:** Submit a selected question, get back the answer.

**Form data expected:** `question_id` (string, must match a key in `queries.QUESTION_REGISTRY`)

**Behavior:**
1. Look up `question_id` in `QUESTION_REGISTRY`. If not found, return HTTP 400 with a clear error — this should never happen from the UI itself (only fixed question buttons are rendered) but must fail cleanly if it does (e.g., a malformed request during testing).
2. Call the corresponding function with `subject_id`.
3. Render the result:
   - If `insufficient_evidence` is True → render the "Insufficient evidence — no supporting records found" state.
   - Otherwise → render the answer, the supporting data rows, and their citations.

**Renders:** `templates/qa.html` (with `result` populated)

**Template context:**
```python
{
  "subject_id": int,
  "question_id": str,
  "question_text": str,
  "result": QueryResult,   # includes .insufficient_evidence, .answer_text, .rows, .citations
}
```

---

### 2.5 `GET /about`
**Purpose:** Static page containing the required safety notice, a plain-language description of the tool's limitations (100-patient sample, no notes, deidentified/date-shifted data, research-only), and a link to the evaluation report.

**Renders:** `templates/about.html` (static content, no DB query)

---

### 2.6 `GET /health`
**Purpose:** Trivial route for local dev sanity-checking that the app and DB connection are alive. Not part of the demo.

**Returns:** `{"status": "ok"}` as JSON, HTTP 200. If the DB connection fails, return `{"status": "error", "detail": "..."}`, HTTP 500.

## 3. Fixed Question Registry (`app/queries.py`)

This is the exhaustive list of supported questions for the hackathon submission. The coding agent should implement exactly these unless the team explicitly adds more — do not invent additional questions without updating this table.

| question_id | Question text (shown in UI) | Tables involved |
|---|---|---|
| `icu_labs` | "What labs did this patient have during their ICU stay(s)?" | labevents, icustays, d_labitems |
| `meds_by_admission` | "What medications were administered during this admission?" | prescriptions, admissions |
| `admission_count` | "How many times was this patient admitted?" | admissions |
| `diagnoses_list` | "What diagnoses were recorded for this patient?" | diagnoses_icd, d_icd_diagnoses |
| `ever_in_icu` | "Was this patient ever transferred to the ICU?" | icustays, transfers |
| `procedures_list` | "What procedures were performed during this patient's stay(s)?" | procedures_icd, d_icd_procedures |
| `los_summary` | "How long was this patient's ICU stay (if any)?" | icustays |

Each question function signature:
```python
def answer_<question_id>(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    ...
```

## 4. Data Contracts (shared dataclasses, defined in `app/citations.py`)

```python
@dataclass
class Citation:
    table: str
    row_id: str          # stringified, may be composite e.g. "hadm_id=123, seq_num=2"
    timestamp: str | None

@dataclass
class TimelineEvent:
    event_type: str       # "admission" | "transfer" | "lab" | "medication" | "diagnosis" | "procedure" | "vital"
    description: str      # human-readable, e.g. "Hemoglobin: 10.2 g/dL (LOW)"
    timestamp: str | None
    citations: list[Citation]

@dataclass
class QueryResult:
    question_id: str
    answer_text: str
    rows: list[dict]
    citations: list[Citation]
    insufficient_evidence: bool = False
```

## 5. Error Response Conventions

| Situation | Behavior |
|---|---|
| Unknown `subject_id` | HTTP 404, render "Patient not found" template |
| Unknown `question_id` | HTTP 400, render generic error template |
| DB connection failure | HTTP 500, render generic error template, log full exception server-side (never show a raw traceback to the user in the demo) |
| Query returns zero rows (valid case) | HTTP 200, render `insufficient_evidence` state — this is NOT an error, it's a correct answer |

## 6. What This API Deliberately Does Not Have

- No authentication — not needed for a local hackathon demo.
- No free-text question input endpoint — out of scope per `PRD.md` Section 6.2.
- No write/update/delete routes — this is a read-only research tool; source data is never modified.
- No pagination — the Demo dataset (100 patients, one at a time) is small enough that full timelines render without it.
