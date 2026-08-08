# PRD.md — Smarter Patient Care: Structured Patient Timeline & Evidence Retrieval

## 1. Overview

**Project name:** PatientTrace (working title)
**Hackathon:** SGTDP AI Hackathon — "AI for Smarter Patient Care"
**Track:** Track 1 — Structured Patient Timeline & Evidence Retrieval
**Timeframe:** 2-day hackathon build
**Team size:** 4

**One-line description:** A tool that reconstructs a single patient's hospital encounter from MIMIC-IV's relational tables into a readable, time-ordered timeline, and answers a fixed set of structured questions about that patient — with every displayed fact traceable back to its exact source table, row, and timestamp.

## 2. Problem Statement

Hospital data in MIMIC-IV is split across many linked relational tables (admissions, transfers, lab results, prescriptions, diagnoses, procedures, ICU chart events). No single table tells the story of a patient's stay. A researcher who wants to answer a simple question — "what happened to this patient during their ICU stay?" — must manually write and reconcile several SQL joins every time.

This project builds a decision-support **research tool**, not a clinical tool. It does not diagnose, recommend treatment, or provide emergency guidance. It exists to make structured hospital data easier to inspect, trust, and study.

## 3. Target User

**Primary user:** Clinical-data researchers, health informatics students, and data-quality/governance teams who need to explore a patient record quickly and verify the underlying data is what they think it is.

**Explicitly NOT the user:** Clinicians making real patient-care decisions. Nothing in this tool should be usable, or interpretable, as clinical guidance.

## 4. Goals

1. Reconstruct any one of the 100 patients in the MIMIC-IV Demo dataset into a single, time-ordered timeline spanning admissions, transfers, labs, medications, diagnoses, procedures, and ICU chart events.
2. Answer a fixed set of pre-defined structured questions about a selected patient, using only data that exists in the supplied tables.
3. Attach a citation (source table, row identifier, timestamp) to every fact shown on screen — no fact may be displayed without a traceable source.
4. Safely abstain ("insufficient evidence") when a question has no supporting data, rather than guessing or hallucinating an answer.
5. Produce a written evaluation report showing accuracy on a sample of manually verified facts, compared against a simple baseline.

## 5. Non-Goals

- No diagnosis, treatment recommendation, triage, or risk prediction.
- No free-text clinical notes (MIMIC-IV Demo does not include them; MIMIC-IV-Note is out of scope).
- No open-ended natural language question answering — only a fixed, documented set of question templates.
- No claims of clinical validity, generalizability, or real-world performance. The dataset is 100 patients from one hospital and is explicitly too small for that.
- No external patient-level data of any kind.

## 6. Core Features (Required Deliverables)

### 6.1 Patient Timeline View
- User selects a patient (by `subject_id`, from a dropdown of the 100 available patients).
- Tool displays a single time-ordered list of all events for that patient across all admissions:
  - Admissions (admit/discharge time, admission type, location)
  - Transfers (ward changes, ICU entry/exit)
  - Lab results (test name, value, unit, flag if abnormal, all from `labevents` joined to `d_labitems`)
  - Prescriptions (drug, dose, route, start/stop time)
  - Diagnoses (ICD code + description, joined to `d_icd_diagnoses`)
  - Procedures (ICD code + description, joined to `d_icd_procedures`)
  - ICU chart events / vitals (selected key vitals from `chartevents`, joined to `d_items`)
- Every event row displays a citation tag: `[table_name, row_id, timestamp]`.
- Events with missing or null timestamps are shown in a separate "undated events" section rather than silently dropped or mis-sorted.

### 6.2 Structured Question-Answering
- A fixed panel of supported questions (buttons or dropdown, NOT a free-text box), for example:
  - "What labs did this patient have during their ICU stay(s)?"
  - "What medications were administered on [date]?"
  - "How many times was this patient admitted?"
  - "What diagnoses were recorded for this patient?"
  - "Was this patient ever transferred to the ICU?"
- Each question maps to a fixed, auditable SQL query — not a free-text LLM call.
- Every answer includes the supporting rows and their citations.
- If a question's supporting data doesn't exist for the selected patient (e.g., "ICU labs" for a patient never admitted to ICU), the tool must explicitly say **"Insufficient evidence — no supporting records found"** rather than returning an empty-looking table with no explanation.

### 6.3 Safety Notice
- The following notice must be visible on every screen, without exception:
  > "Research and educational prototype only. Not for clinical use. Do not use for diagnosis, treatment, triage, or emergency decisions."

### 6.4 Evaluation Report (deliverable document, not a UI feature)
- Manually select 15–20 facts across 3+ patients.
- Verify each fact is correctly retrieved and correctly cited by the tool.
- Report accuracy (e.g., "18/20 correct") and describe every failure case honestly.
- Compare against a stated baseline (see Section 8).

## 7. Success Criteria

- Tool runs end-to-end for at least 3 different patients without crashing.
- 100% of facts displayed in the UI carry a visible citation.
- The tool correctly abstains (does not fabricate an answer) on at least one deliberately tested "no data" case.
- Evaluation report shows accuracy ≥ 90% on the manually verified sample, with failures documented, not hidden.
- Safety notice is present on every page of the UI.

## 8. Baseline (Required Comparison)

**Baseline definition:** Manually querying a single table (e.g., `labevents` alone, without joining to `admissions`, `icustays`, or `d_labitems`) to answer the same question set.

**What this demonstrates:** The baseline will fail to answer any question requiring context across tables (e.g., "labs during the ICU stay" requires joining `labevents` to `icustays` on time and `hadm_id`) and will show raw `itemid` codes instead of readable lab names. The evaluation report should show, side by side, how many of the sample questions the baseline can answer correctly versus how many the full tool answers correctly.

## 9. Data Source

- **Dataset:** MIMIC-IV Clinical Database Demo v2.2 (PhysioNet), 100 patients, deidentified, date-shifted.
- **Tables used:** `patients`, `admissions`, `transfers`, `icustays`, `labevents`, `d_labitems`, `prescriptions`, `diagnoses_icd`, `d_icd_diagnoses`, `procedures_icd`, `d_icd_procedures`, `chartevents`, `d_items`.
- Full table specifications are in `DATABASE.md`.
- **License:** PhysioNet Credentialed Health Data License (or Demo-specific open license — confirm on the download page). Cite the required paper/dataset citation from the official MIMIC-IV Demo page in the final submission.

## 10. Constraints & Rules (from the challenge brief)

- Use the organizer-supplied frozen copy of MIMIC-IV Demo v2.2 as the primary dataset.
- No external patient-level data.
- No free-text clinical notes may be simulated, generated, or presented as if clinician-authored.
- All models/rules/manual labels used must be disclosed.
- Any data sent to external services (if any) must be minimized and disclosed.

## 11. Out of Scope for This Hackathon

- Predictive modeling (that's Track 3 — not selected).
- Cohort-level analytics across all 100 patients (that's Track 2 — not selected; may be a stretch goal only if core deliverables are complete early).
- Any UI polish beyond what's needed to clearly demonstrate the timeline and Q&A features.

## 12. Deliverables Checklist (map to hackathon submission requirements)

- [ ] Working prototype (Flask app, end-to-end demo)
- [ ] Source code + run instructions (this repo + `DEVELOPMENT.md`)
- [ ] Technical summary (`ARCHITECTURE.md` + this `PRD.md`)
- [ ] Evaluation report (`docs/evaluation_report.md`)
- [ ] Safety and data statement (`docs/safety_statement.md`)
- [ ] Demo and pitch (5-minute walkthrough: hero patient, one Q&A example, one honest failure case)
