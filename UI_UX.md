# UI_UX.md — UI/UX Specification

## 1. Design Principles

1. **Clarity over polish.** This is judged on correctness and traceability (rubric: AI & Data Quality 25%, Safety & Reliability 15%), not visual design (not a separate rubric line at all). Do not spend hackathon time on animations, custom illustrations, or elaborate theming.
2. **Every fact shows its source.** This is the single non-negotiable UI rule. No number, label, or claim appears on screen without a visible citation next to it.
3. **Three visually distinct states, always.** "Data found and shown," "no data found (insufficient evidence)," and "something went wrong (error)" must never look the same. Use color/icon/wording to make these unmistakably different at a glance.
4. **Safety notice is persistent, not optional.** It appears in the same place on every page, unmissable, never behind a click or a collapsed section.

## 2. Tech for Styling

- Bootstrap 5 via CDN (no build step, no npm install — just a `<link>` and `<script>` tag in `base.html`). Faster to get a clean, readable layout than hand-rolled CSS on a 2-day clock.
- One small custom stylesheet (`static/style.css`) for citation tag styling and the three state colors.
- No JS framework. Vanilla JS (`static/script.js`) only if you want a citation tooltip-on-hover; otherwise citations can just render inline as small text and no JS is needed at all.

## 3. Page-by-Page Spec

### 3.1 `base.html` (shared layout, all pages extend this)

```
┌──────────────────────────────────────────────────────────┐
│  PatientTrace                              [About] [Home] │  ← top nav bar
├──────────────────────────────────────────────────────────┤
│  ⚠ Research and educational prototype only. Not for      │  ← persistent safety
│    clinical use. Do not use for diagnosis, treatment,     │    banner, yellow/
│    triage, or emergency decisions.                        │    amber background
├──────────────────────────────────────────────────────────┤
│                                                            │
│                  {% block content %}                      │
│                                                            │
└──────────────────────────────────────────────────────────┘
```
- Safety banner: Bootstrap `alert alert-warning`, fixed at the top, same on every page.
- Nav bar: simple, just "Home" and "About" links — no need for anything more.

### 3.2 `index.html` (`GET /`)

```
┌──────────────────────────────────────────────────────────┐
│  Select a patient to view their timeline                  │
│                                                            │
│  [ Search / filter box            ]                       │
│                                                            │
│  ┌────────────┬────────┬──────────┬─────────────────┐    │
│  │ subject_id │ gender │ age      │                  │    │
│  ├────────────┼────────┼──────────┼─────────────────┤    │
│  │ 10004235   │ F      │ 66       │ [View Timeline]  │    │
│  │ 10006053   │ M      │ 45       │ [View Timeline]  │    │
│  │ ...        │        │          │                  │    │
│  └────────────┴────────┴──────────┴─────────────────┘    │
└──────────────────────────────────────────────────────────┘
```
- A simple sortable/filterable table (Bootstrap table classes are enough; a JS datatable library is not needed for 100 rows).
- Each row's "View Timeline" button links to `/patient/<subject_id>`.

### 3.3 `timeline.html` (`GET /patient/<subject_id>`)

```
┌──────────────────────────────────────────────────────────┐
│  Patient 10004235 — F, age 66            [Ask a Question] │
├──────────────────────────────────────────────────────────┤
│  ● 2023-01-03 08:15  ADMISSION                            │
│    Admitted via EW EMER. to Medicine                      │
│    [source: admissions, hadm_id=25123456]                 │
│                                                            │
│  ● 2023-01-03 10:02  LAB                                  │
│    Hemoglobin: 10.2 g/dL  ⚠ LOW                            │
│    [source: labevents, labevent_id=8834211]                │
│                                                            │
│  ● 2023-01-03 14:30  MEDICATION                           │
│    Furosemide 40mg, IV                                    │
│    [source: prescriptions, pharmacy_id=44201, 2023-01-03] │
│                                                            │
│  ● 2023-01-04 02:15  TRANSFER                              │
│    Transferred to Medical ICU (MICU)                       │
│    [source: transfers, transfer_id=991823]                 │
│                                                            │
│  ... (continues, time-ordered) ...                         │
├──────────────────────────────────────────────────────────┤
│  ⚠ Events with missing/unknown timestamps (3)              │
│    ▸ [expand to view]                                      │
└──────────────────────────────────────────────────────────┘
```

**Visual conventions:**
- Each event type gets a small colored badge/icon (e.g., admission = blue, lab = purple, medication = green, transfer = orange, diagnosis = gray, procedure = teal, vital = red) so the timeline is scannable at a glance without reading every line.
- Abnormal lab flags (`flag = 'abnormal'`) get a visible `⚠` marker — this is directly sourced from the `flag` column, not inferred.
- Citation text is small, muted gray, monospace font, in the format `[source: table_name, row_id]` — visually distinct from the main event description.
- The "undated events" section is collapsed by default (Bootstrap collapse component) so it doesn't clutter the primary reading experience, but is never hidden or omitted entirely.

### 3.4 `qa.html` (`GET`/`POST /patient/<subject_id>/ask`)

**Initial state (GET, no question submitted yet):**
```
┌──────────────────────────────────────────────────────────┐
│  Ask about Patient 10004235                                │
│                                                            │
│  ○ What labs did this patient have during their ICU stay?  │
│  ○ What medications were administered during this          │
│     admission?                                              │
│  ○ How many times was this patient admitted?                │
│  ○ What diagnoses were recorded for this patient?           │
│  ○ Was this patient ever transferred to the ICU?            │
│  ○ What procedures were performed?                          │
│  ○ How long was this patient's ICU stay?                    │
│                                                            │
│              [ Submit Question ]                            │
└──────────────────────────────────────────────────────────┘
```
- Radio buttons or a simple dropdown, NOT a free-text box — reinforces that this is a fixed, auditable question set, not an open LLM prompt.

**Answer state (POST result, data found):**
```
┌──────────────────────────────────────────────────────────┐
│  Q: What labs did this patient have during their ICU stay?  │
│                                                              │
│  ✅ Found 4 supporting records.                              │
│                                                              │
│  ┌──────────────┬────────┬──────┬───────────────────────┐  │
│  │ Lab          │ Value  │ Flag │ Source                 │  │
│  ├──────────────┼────────┼──────┼───────────────────────┤  │
│  │ Hemoglobin   │ 10.2   │ LOW  │ labevents #8834211     │  │
│  │ WBC          │ 11.4   │      │ labevents #8834219     │  │
│  │ ...          │        │      │                        │  │
│  └──────────────┴────────┴──────┴───────────────────────┘  │
│                                                              │
│              [ Ask Another Question ]                        │
└──────────────────────────────────────────────────────────┘
```

**Answer state (POST result, no data — insufficient evidence):**
```
┌──────────────────────────────────────────────────────────┐
│  Q: Was this patient ever transferred to the ICU?           │
│                                                              │
│  ⚪ Insufficient evidence — no supporting records found.     │
│     This patient has no records in the icustays or           │
│     transfers tables indicating ICU admission.                │
│                                                              │
│              [ Ask Another Question ]                        │
└──────────────────────────────────────────────────────────┘
```
- **This is the most important screen to get right for the demo.** Use a neutral gray/blue color here (not red — this isn't an error, it's a correct, honest answer) with a distinct icon from both the success state (green checkmark) and the error state (red X), so a judge watching the demo immediately understands "the tool correctly said it doesn't know" rather than "the tool is broken."

### 3.5 `about.html` (`GET /about`, static)

Content sections, in order:
1. Safety notice (repeated, larger, in full — not just the banner version).
2. "What this tool does" (2-3 sentences, plain language).
3. "What this tool does not do" — explicit list: no diagnosis, no treatment advice, no clinical validity claims, not generalizable beyond this 100-patient sample.
4. "Data source" — MIMIC-IV Demo v2.2, citation, license note, dates are shifted/deidentified.
5. Link to the evaluation report (`docs/evaluation_report.md`, rendered as plain text or linked as a download).

### 3.6 Error / Not Found page (`404`, `500`, `400` handlers)

```
┌──────────────────────────────────────────────────────────┐
│  ❌ Patient not found                                       │
│                                                              │
│  No patient with ID 99999999 exists in this dataset.         │
│                                                              │
│              [ Return to Patient List ]                      │
└──────────────────────────────────────────────────────────┘
```
- Red/error color, clearly distinct from the "insufficient evidence" state above. This distinction matters for the demo: "no such patient" is a different kind of "no" than "this patient exists but has no data for this question."

## 4. Color & State Legend (apply consistently across all templates)

| State | Color | Icon |
|---|---|---|
| Data found / success | Green | ✅ |
| Insufficient evidence (correct, honest "don't know") | Gray/blue | ⚪ or ℹ️ |
| Error (bad input, system failure) | Red | ❌ |
| Warning (abnormal lab, safety notice) | Amber/yellow | ⚠️ |

## 5. Accessibility / Practical Notes

- Use semantic HTML (`<table>` for tabular data, not divs) — faster to build correctly with Bootstrap classes anyway.
- Keep font sizes and contrast reasonable for a live demo projected on a screen — test the timeline page on a projector or shared screen before the pitch, not just on a laptop.
- No mobile responsiveness work needed — this will be demoed on a laptop, not a phone. Don't spend time on it.

## 6. Explicitly Out of Scope for UI

- No dark mode.
- No user accounts / login.
- No animations or transitions beyond Bootstrap defaults.
- No custom logo/branding beyond a simple text title ("PatientTrace") in the nav bar.
