"""
app/queries.py
==============
Structured question-answering functions and QUESTION_REGISTRY for Smarter Patient Care.

Per API.md Section 3:
All functions take (subject_id: int, conn: sqlite3.Connection) -> QueryResult.
No ML models, no external API calls, no guessing or hallucination.
If no supporting rows exist, return QueryResult(insufficient_evidence=True).
"""

import sqlite3
from typing import Dict, Callable, Any

from app.citations import Citation, QueryResult


def answer_icu_labs(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'What labs did this patient have during their ICU stay(s)?'
    Tables: labevents, icustays, d_labitems
    """
    qid = "icu_labs"
    query = """
        SELECT l.labevent_id, l.charttime, l.itemid, l.value, l.valuenum, l.valueuom, l.flag,
               d.label, i.stay_id, i.intime AS icu_intime, i.outtime AS icu_outtime
        FROM labevents l
        JOIN icustays i ON l.subject_id = i.subject_id 
                       AND l.charttime >= i.intime 
                       AND l.charttime <= i.outtime
        LEFT JOIN d_labitems d ON l.itemid = d.itemid
        WHERE l.subject_id = ?
        ORDER BY l.charttime ASC
    """
    rows = []
    citations = []
    
    for r in conn.execute(query, (subject_id,)):
        lab_id = r["labevent_id"]
        stay_id = r["stay_id"]
        charttime = r["charttime"]
        label = r["label"] or f"Lab {r['itemid']}"
        val = r["value"] or (str(r["valuenum"]) if r["valuenum"] is not None else "")
        uom = r["valueuom"] or ""
        flag = r["flag"] or ""

        val_str = f"{val} {uom}".strip()
        if flag:
            val_str += f" ({flag.upper()})"

        row_dict = {
            "labevent_id": lab_id,
            "stay_id": stay_id,
            "charttime": charttime,
            "label": label,
            "value": val_str,
        }
        rows.append(row_dict)

        citations.append(Citation(table="labevents", row_id=f"labevent_id={lab_id}", timestamp=charttime))
        citations.append(Citation(table="icustays", row_id=f"stay_id={stay_id}", timestamp=r["icu_intime"]))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No ICU lab events found for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Found {len(rows)} lab measurement(s) during ICU stay(s)."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_meds_by_admission(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'What medications were administered during this admission?'
    Tables: prescriptions, admissions
    """
    qid = "meds_by_admission"
    query = """
        SELECT p.subject_id, p.hadm_id, p.pharmacy_id, p.starttime, p.stoptime,
               p.drug, p.dose_val_rx, p.dose_unit_rx, p.route, a.admittime
        FROM prescriptions p
        JOIN admissions a ON p.subject_id = a.subject_id AND p.hadm_id = a.hadm_id
        WHERE p.subject_id = ?
        ORDER BY p.starttime ASC
    """
    rows = []
    citations = []

    for r in conn.execute(query, (subject_id,)):
        pharmacy_id = r["pharmacy_id"]
        hadm_id = r["hadm_id"]
        starttime = r["starttime"]
        drug = r["drug"] or "Unknown Drug"
        dose = r["dose_val_rx"] or ""
        unit = r["dose_unit_rx"] or ""
        route = r["route"] or ""

        row_dict = {
            "hadm_id": hadm_id,
            "pharmacy_id": pharmacy_id,
            "starttime": starttime,
            "drug": drug,
            "dose": f"{dose} {unit}".strip(),
            "route": route,
        }
        rows.append(row_dict)

        citations.append(Citation(
            table="prescriptions",
            row_id=f"pharmacy_id={pharmacy_id}, starttime={starttime}",
            timestamp=starttime
        ))
        citations.append(Citation(
            table="admissions",
            row_id=f"hadm_id={hadm_id}",
            timestamp=r["admittime"]
        ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No medication prescription records found for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Found {len(rows)} prescription record(s) across admissions."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_admission_count(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'How many times was this patient admitted?'
    Tables: admissions
    """
    qid = "admission_count"
    query = """
        SELECT hadm_id, admittime, dischtime, admission_type, admission_location
        FROM admissions
        WHERE subject_id = ?
        ORDER BY admittime ASC
    """
    rows = []
    citations = []

    for r in conn.execute(query, (subject_id,)):
        hadm_id = r["hadm_id"]
        admittime = r["admittime"]

        rows.append({
            "hadm_id": hadm_id,
            "admittime": admittime,
            "dischtime": r["dischtime"],
            "admission_type": r["admission_type"],
            "admission_location": r["admission_location"],
        })
        citations.append(Citation(
            table="admissions",
            row_id=f"hadm_id={hadm_id}",
            timestamp=admittime
        ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No hospital admission records found for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    count = len(rows)
    ans_text = f"This patient was admitted {count} time(s)."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_diagnoses_list(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'What diagnoses were recorded for this patient?'
    Tables: diagnoses_icd, d_icd_diagnoses
    """
    qid = "diagnoses_list"
    query = """
        SELECT diag.hadm_id, diag.seq_num, diag.icd_code, diag.icd_version, d.long_title
        FROM diagnoses_icd diag
        LEFT JOIN d_icd_diagnoses d ON diag.icd_code = d.icd_code AND diag.icd_version = d.icd_version
        WHERE diag.subject_id = ?
        ORDER BY diag.hadm_id, diag.seq_num ASC
    """
    rows = []
    citations = []

    for r in conn.execute(query, (subject_id,)):
        hadm_id = r["hadm_id"]
        seq_num = r["seq_num"]
        icd_code = r["icd_code"]
        icd_version = r["icd_version"]
        title = r["long_title"] or f"ICD-{icd_version} {icd_code}"

        rows.append({
            "hadm_id": hadm_id,
            "seq_num": seq_num,
            "icd_code": icd_code,
            "icd_version": icd_version,
            "title": title,
        })
        citations.append(Citation(
            table="diagnoses_icd",
            row_id=f"hadm_id={hadm_id}, seq_num={seq_num}",
            timestamp=None
        ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No recorded diagnoses found for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Recorded {len(rows)} diagnosis code(s) for this patient."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_ever_in_icu(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'Was this patient ever transferred to the ICU?'
    Tables: icustays, transfers
    """
    qid = "ever_in_icu"
    icu_query = """
        SELECT stay_id, hadm_id, first_careunit, last_careunit, intime, outtime, los
        FROM icustays
        WHERE subject_id = ?
        ORDER BY intime ASC
    """
    rows = []
    citations = []

    for r in conn.execute(icu_query, (subject_id,)):
        stay_id = r["stay_id"]
        intime = r["intime"]
        rows.append({
            "stay_id": stay_id,
            "hadm_id": r["hadm_id"],
            "unit": r["first_careunit"],
            "intime": intime,
            "outtime": r["outtime"],
            "los_days": r["los"],
        })
        citations.append(Citation(
            table="icustays",
            row_id=f"stay_id={stay_id}",
            timestamp=intime
        ))

    if not rows:
        # Fallback check transfers table for ICU careunits
        trans_query = """
            SELECT transfer_id, hadm_id, careunit, intime, outtime
            FROM transfers
            WHERE subject_id = ? AND careunit LIKE '%ICU%'
            ORDER BY intime ASC
        """
        for r in conn.execute(trans_query, (subject_id,)):
            t_id = r["transfer_id"]
            intime = r["intime"]
            rows.append({
                "transfer_id": t_id,
                "hadm_id": r["hadm_id"],
                "unit": r["careunit"],
                "intime": intime,
                "outtime": r["outtime"],
            })
            citations.append(Citation(
                table="transfers",
                row_id=f"transfer_id={t_id}",
                timestamp=intime
            ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No ICU stay or ICU transfer records found. Patient was not admitted to the ICU.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Yes, this patient has {len(rows)} recorded ICU stay/transfer event(s)."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_procedures_list(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'What procedures were performed during this patient's stay(s)?'
    Tables: procedures_icd, d_icd_procedures
    """
    qid = "procedures_list"
    query = """
        SELECT proc.hadm_id, proc.seq_num, proc.chartdate, proc.icd_code, proc.icd_version, d.long_title
        FROM procedures_icd proc
        LEFT JOIN d_icd_procedures d ON proc.icd_code = d.icd_code AND proc.icd_version = d.icd_version
        WHERE proc.subject_id = ?
        ORDER BY proc.chartdate ASC, proc.seq_num ASC
    """
    rows = []
    citations = []

    for r in conn.execute(query, (subject_id,)):
        hadm_id = r["hadm_id"]
        seq_num = r["seq_num"]
        chartdate = r["chartdate"]
        icd_code = r["icd_code"]
        icd_version = r["icd_version"]
        title = r["long_title"] or f"Procedure {icd_code}"

        rows.append({
            "hadm_id": hadm_id,
            "seq_num": seq_num,
            "chartdate": chartdate,
            "icd_code": icd_code,
            "icd_version": icd_version,
            "title": title,
        })
        citations.append(Citation(
            table="procedures_icd",
            row_id=f"hadm_id={hadm_id}, seq_num={seq_num}",
            timestamp=chartdate
        ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No procedure records found for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Found {len(rows)} recorded procedure(s)."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


def answer_los_summary(subject_id: int, conn: sqlite3.Connection) -> QueryResult:
    """
    Question: 'How long was this patient's ICU stay (if any)?'
    Tables: icustays
    """
    qid = "los_summary"
    query = """
        SELECT stay_id, hadm_id, first_careunit, intime, outtime, los
        FROM icustays
        WHERE subject_id = ?
        ORDER BY intime ASC
    """
    rows = []
    citations = []
    total_los = 0.0

    for r in conn.execute(query, (subject_id,)):
        stay_id = r["stay_id"]
        intime = r["intime"]
        los_val = r["los"] if r["los"] is not None else 0.0
        total_los += los_val

        rows.append({
            "stay_id": stay_id,
            "hadm_id": r["hadm_id"],
            "unit": r["first_careunit"],
            "intime": intime,
            "outtime": r["outtime"],
            "los_days": round(los_val, 2),
        })
        citations.append(Citation(
            table="icustays",
            row_id=f"stay_id={stay_id}",
            timestamp=intime
        ))

    if not rows:
        return QueryResult(
            question_id=qid,
            answer_text="No ICU stays recorded for this patient.",
            rows=[],
            citations=[],
            insufficient_evidence=True
        )

    ans_text = f"Total ICU length of stay: {round(total_los, 2)} day(s) across {len(rows)} stay(s)."
    return QueryResult(
        question_id=qid,
        answer_text=ans_text,
        rows=rows,
        citations=citations,
        insufficient_evidence=False
    )


# ---------------------------------------------------------------------------
# QUESTION_REGISTRY Dict (API.md Section 3)
# ---------------------------------------------------------------------------
QUESTION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "icu_labs": {
        "text": "What labs did this patient have during their ICU stay(s)?",
        "func": answer_icu_labs,
    },
    "meds_by_admission": {
        "text": "What medications were administered during this admission?",
        "func": answer_meds_by_admission,
    },
    "admission_count": {
        "text": "How many times was this patient admitted?",
        "func": answer_admission_count,
    },
    "diagnoses_list": {
        "text": "What diagnoses were recorded for this patient?",
        "func": answer_diagnoses_list,
    },
    "ever_in_icu": {
        "text": "Was this patient ever transferred to the ICU?",
        "func": answer_ever_in_icu,
    },
    "procedures_list": {
        "text": "What procedures were performed during this patient's stay(s)?",
        "func": answer_procedures_list,
    },
    "los_summary": {
        "text": "How long was this patient's ICU stay (if any)?",
        "func": answer_los_summary,
    },
}
