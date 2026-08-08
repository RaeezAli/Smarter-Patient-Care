# ARCHITECTURE.md — System Architecture

## 1. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser (User)                        │
└───────────────────────────┬────────────────────────────────┘
                             │ HTTP (GET/POST)
┌───────────────────────────▼────────────────────────────────┐
│                       Flask App (app/)                       │
│  ┌───────────────┐   ┌────────────────┐   ┌───────────────┐ │
│  │  routes.py     │──▶│  timeline.py    │──▶│   db.py       │ │
│  │  (HTTP layer)  │   │  queries.py     │   │  (SQLite conn)│ │
│  │                │   │  citations.py   │   │               │ │
│  └───────┬────────┘   └────────────────┘   └───────┬───────┘ │
│          │                                          │        │
│          ▼                                          ▼        │
│    templates/*.html                          data/mimic.db   │
│    (Jinja2 rendering)                        (SQLite file)   │
└────────────────────────────────────────────────────────────┘
```

**Design principle:** No ML models, no external API calls, no network dependency at runtime. Everything is deterministic Python + SQL. This eliminates an entire category of demo-day failure (API downtime, model non-determinism, latency spikes) and matches the rubric's emphasis on reproducibility and traceability over technical sophistication.

## 2. Component Responsibilities

### 2.1 `scripts/load_data.py` (one-time, run before the app starts)
- Reads the raw MIMIC-IV Demo CSVs from `data/raw/`.
- Loads each CSV into a corresponding table in `data/mimic.db` (SQLite).
- Applies basic type coercion (parse datetime columns, preserve leading zeros in code fields, do not silently drop nulls).
- Idempotent: safe to re-run; drops and recreates tables each time.
- Logs row counts per table after loading, so the team can sanity-check nothing silently failed.

### 2.2 `scripts/build_indexes.py` (one-time, run after load_data.py)
- Adds indexes on `subject_id`, `hadm_id`, and `stay_id` across relevant tables to keep query latency low, especially on `labevents` and `chartevents`, which are the largest tables even in the Demo subset.

### 2.3 `app/db.py`
- Owns the single SQLite connection factory used by the rest of the app.
- Exposes one function: `get_db_connection() -> sqlite3.Connection`.
- Sets `row_factory = sqlite3.Row` so query results can be accessed by column name (needed throughout `timeline.py` and `citations.py`).
- No other file should open its own raw `sqlite3.connect()` call — always go through this module, so connection handling stays centralized and swappable later if needed.

### 2.4 `app/timeline.py`
- Core function: `get_patient_timeline(subject_id: int) -> list[TimelineEvent]`.
- Queries every relevant table for the given `subject_id`, joined against dictionary tables (`d_labitems`, `d_items`, `d_icd_diagnoses`, `d_icd_procedures`) to produce human-readable labels instead of raw codes.
- Merges all events into a single list, sorted by timestamp.
- Events with a null/missing timestamp are returned in a separate list (`undated_events`), never silently dropped, never sorted arbitrarily into the timeline.
- Each returned event is wrapped with a citation via `citations.py` before being returned — the timeline function never returns a "naked" fact without a source.

### 2.5 `app/queries.py`
- Contains the fixed set of supported question templates (see `API.md` Section 3 for the full list).
- Each question is implemented as its own function, e.g. `answer_icu_labs(subject_id, conn) -> QueryResult`.
- Each function either returns a populated `QueryResult` (with citations) or an explicit `QueryResult(insufficient_evidence=True)` — there is no code path that returns a guessed or inferred answer.
- New questions are added by writing a new function here and registering it in the `QUESTION_REGISTRY` dict at the bottom of the file — this is the single place the coding agent should look when asked to add a new supported question.

### 2.6 `app/citations.py`
- Defines the `Citation` dataclass: `{table: str, row_id: str, timestamp: str | None}`.
- Defines `TimelineEvent` and `QueryResult` dataclasses, both of which require a `citations: list[Citation]` field — this is enforced at the type level so a fact cannot be constructed without at least one citation attached (except explicit `insufficient_evidence` results, which carry an empty citation list by design).

### 2.7 `app/routes.py`
- Thin HTTP layer. Each route calls into `timeline.py` / `queries.py`, then renders a template with the result.
- No business logic should live in `routes.py` — if a route function is doing anything beyond "parse request → call backend function → render template," that logic belongs in `timeline.py` or `queries.py` instead.
- Full route list is in `API.md`.

### 2.8 `app/templates/*.html`
- Server-rendered Jinja2 templates. No client-side framework.
- `base.html` contains the persistent safety notice (see `UI_UX.md`) and shared layout.
- `timeline.html` and `qa.html` extend `base.html`.

### 2.9 `app/static/`
- `style.css` — styling, loaded via CDN Bootstrap or Tailwind plus a small custom override file.
- `script.js` — minimal vanilla JS only if needed for interactivity (e.g., toggling citation tooltips). No JS framework, no build step.

## 3. Data Flow (Example: User views a patient timeline)

1. User selects `subject_id = 10004235` from the dropdown on the home page and submits.
2. Browser sends `GET /patient/10004235`.
3. `routes.py` receives the request, calls `timeline.get_patient_timeline(10004235)`.
4. `timeline.py` opens a connection via `db.py`, runs the per-table queries, joins dictionary tables, merges and sorts events, wraps each in a `Citation`.
5. `routes.py` passes the resulting `list[TimelineEvent]` to `templates/timeline.html`.
6. Jinja2 renders the timeline, including citation tags, into HTML.
7. Browser displays the page.

## 4. Data Flow (Example: User asks a structured question)

1. User selects "What labs did this patient have during their ICU stay?" from the question panel for the currently selected patient.
2. Browser sends `POST /ask` with `subject_id` and `question_id`.
3. `routes.py` looks up the corresponding function in `queries.QUESTION_REGISTRY`, calls it with `subject_id`.
4. The function runs its SQL, and either:
   - Finds supporting rows → builds a `QueryResult` with the answer text, supporting rows, and citations, OR
   - Finds no supporting rows → returns `QueryResult(insufficient_evidence=True)`.
5. `routes.py` renders `templates/qa.html` (or a partial) with the result.
6. If `insufficient_evidence` is True, the template renders the "Insufficient evidence — no supporting records found" message instead of an empty table.

## 5. Error Handling Principles

- **Never fail silently.** If a query returns zero rows, that must be visibly distinguished from "the tool is broken" — always render an explicit state (empty state vs. error state vs. insufficient-evidence state are three different things and must look different in the UI).
- **Never guess.** If data is ambiguous or missing, the correct behavior is to say so, not to interpolate, infer, or hallucinate a plausible-looking answer.
- **Log, don't crash, on unexpected input.** If a `subject_id` is requested that doesn't exist in the dataset, return a clean "patient not found" page, not a stack trace.

## 6. Why This Architecture (Rationale for the Coding Agent)

- **No ORM.** With a fixed, well-understood schema and a 2-day timeline, raw SQL via `sqlite3` is faster to write and easier for the team to audit than introducing SQLAlchemy's ORM layer. Use parameterized queries (`?` placeholders) everywhere — never string-format `subject_id` into a query, even though this is a hackathon and not a public-facing app with user-supplied SQL injection risk from strangers.
- **No LLM / NLP in this track.** All question-answering is rule-based and pre-defined. This was a deliberate scope decision (see `PRD.md` Section 6.2) to eliminate hallucination risk and keep the evaluation fully auditable, which directly serves the "AI & Data Quality" and "Safety & Reliability" rubric categories.
- **Server-rendered Flask + Jinja2, not a SPA.** No API/frontend contract to maintain, no separate dev server, no build step — reduces integration risk given the compressed timeline.
