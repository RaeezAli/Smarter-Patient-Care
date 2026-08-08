"""
app/timeline.py
================
Timeline generation engine for Smarter Patient Care.

Per ARCHITECTURE.md Section 2.4:
- get_patient_timeline(subject_id: int) -> dict
  Returns: {"timeline_events": list[TimelineEvent], "undated_events": list[TimelineEvent]}
- Queries all 7 event categories for subject_id only.
- Joins dictionary tables for human-readable labels.
- Uses a whitelisted constant for ICU vitals (chartevents).
- Attaches a Citation to every single event.
- Sorts dated events chronologically; places undated events in undated_events list.
"""

from typing import Dict, List, Tuple, Any
import sqlite3

from app.db import get_db_connection
from app.citations import Citation, TimelineEvent

# ---------------------------------------------------------------------------
# Whitelisted Item IDs for ICU Vitals (chartevents)
# ---------------------------------------------------------------------------
# Sourced from MIMIC-IV d_items for key vital signs:
# 220045: Heart Rate (bpm)
# 220179: Non Invasive Blood Pressure systolic (mmHg)
# 220050: Arterial Blood Pressure systolic (mmHg)
# 220210: Respiratory Rate (insp/min)
# 223761: Temperature Fahrenheit (°F)
# 223762: Temperature Celsius (°C)
# 220277: O2 saturation pulseoxymetry / SpO2 (%)
# 220739: Eye Opening (GCS)
# 226755: Verbal Response (GCS)
# 227013: Motor Response (GCS)
VITAL_ITEMIDS = [
    220045, 220179, 220050, 220210,
    223761, 223762, 220277, 220739, 226755, 227013
]


def get_patient_timeline(subject_id: int, conn: sqlite3.Connection = None) -> Dict[str, List[TimelineEvent]]:
    """
    Query all clinical tables for the given subject_id, wrap each in a Citation,
    and return time-sorted dated events and separate undated events.

    Args:
        subject_id: Patient ID
        conn: Optional sqlite3.Connection (if None, get_db_connection() is called)

    Returns:
        Dict with keys "timeline_events" and "undated_events" containing TimelineEvent objects.
    """
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True

    try:
        events: List[TimelineEvent] = []

        # 1. Admissions
        adm_query = """
            SELECT hadm_id, admittime, dischtime, deathtime, admission_type, admission_location, discharge_location
            FROM admissions
            WHERE subject_id = ?
        """
        for row in conn.execute(adm_query, (subject_id,)):
            hadm_id = row["hadm_id"]
            admittime = row["admittime"]
            adm_type = row["admission_type"] or "Hospital Admission"
            adm_loc = row["admission_location"] or "Unknown location"
            disch_loc = row["discharge_location"] or ""
            
            desc = f"Admitted ({adm_type}) from {adm_loc}"
            if disch_loc:
                desc += f" -> Discharged to {disch_loc}"

            citation = Citation(
                table="admissions",
                row_id=f"hadm_id={hadm_id}",
                timestamp=admittime
            )
            events.append(TimelineEvent(
                event_type="admission",
                description=desc,
                timestamp=admittime,
                citations=[citation]
            ))

        # 2. Transfers
        trans_query = """
            SELECT transfer_id, hadm_id, eventtype, careunit, intime, outtime
            FROM transfers
            WHERE subject_id = ?
        """
        for row in conn.execute(trans_query, (subject_id,)):
            transfer_id = row["transfer_id"]
            eventtype = row["eventtype"] or "transfer"
            careunit = row["careunit"] or "Unspecified ward"
            intime = row["intime"]

            desc = f"Unit Transfer ({eventtype}): {careunit}"

            citation = Citation(
                table="transfers",
                row_id=f"transfer_id={transfer_id}",
                timestamp=intime
            )
            events.append(TimelineEvent(
                event_type="transfer",
                description=desc,
                timestamp=intime,
                citations=[citation]
            ))

        # 3. Lab Events
        lab_query = """
            SELECT l.labevent_id, l.itemid, l.charttime, l.value, l.valuenum, l.valueuom, l.flag, d.label
            FROM labevents l
            LEFT JOIN d_labitems d ON l.itemid = d.itemid
            WHERE l.subject_id = ?
        """
        for row in conn.execute(lab_query, (subject_id,)):
            labevent_id = row["labevent_id"]
            charttime = row["charttime"]
            lab_label = row["label"] or f"Lab Item {row['itemid']}"
            val = row["value"] or (str(row["valuenum"]) if row["valuenum"] is not None else "")
            uom = row["valueuom"] or ""
            flag = row["flag"] or ""

            val_str = f"{val} {uom}".strip()
            if flag:
                val_str += f" ({flag.upper()})"
            desc = f"Lab: {lab_label} = {val_str}" if val_str else f"Lab: {lab_label}"

            citation = Citation(
                table="labevents",
                row_id=f"labevent_id={labevent_id}",
                timestamp=charttime
            )
            events.append(TimelineEvent(
                event_type="lab",
                description=desc,
                timestamp=charttime,
                citations=[citation]
            ))

        # 4. Medications (Prescriptions)
        med_query = """
            SELECT subject_id, hadm_id, pharmacy_id, starttime, stoptime, drug, dose_val_rx, dose_unit_rx, route
            FROM prescriptions
            WHERE subject_id = ?
        """
        for row in conn.execute(med_query, (subject_id,)):
            pharmacy_id = row["pharmacy_id"]
            starttime = row["starttime"]
            drug = row["drug"] or "Unknown Drug"
            dose = row["dose_val_rx"] or ""
            unit = row["dose_unit_rx"] or ""
            route = row["route"] or ""

            dose_str = f"{dose} {unit}".strip()
            details = []
            if dose_str:
                details.append(dose_str)
            if route:
                details.append(f"via {route}")
            
            detail_text = f" ({', '.join(details)})" if details else ""
            desc = f"Medication Prescribed: {drug}{detail_text}"

            row_id_str = f"pharmacy_id={pharmacy_id}, starttime={starttime}"
            citation = Citation(
                table="prescriptions",
                row_id=row_id_str,
                timestamp=starttime
            )
            events.append(TimelineEvent(
                event_type="medication",
                description=desc,
                timestamp=starttime,
                citations=[citation]
            ))

        # 5. Diagnoses
        diag_query = """
            SELECT diag.hadm_id, diag.seq_num, diag.icd_code, diag.icd_version, d.long_title
            FROM diagnoses_icd diag
            LEFT JOIN d_icd_diagnoses d ON diag.icd_code = d.icd_code AND diag.icd_version = d.icd_version
            WHERE diag.subject_id = ?
        """
        for row in conn.execute(diag_query, (subject_id,)):
            hadm_id = row["hadm_id"]
            seq_num = row["seq_num"]
            icd_code = row["icd_code"]
            title = row["long_title"] or f"ICD-{row['icd_version']} {icd_code}"
            
            desc = f"Diagnosis #{seq_num}: {title} [{icd_code}]"

            citation = Citation(
                table="diagnoses_icd",
                row_id=f"hadm_id={hadm_id}, seq_num={seq_num}",
                timestamp=None
            )
            events.append(TimelineEvent(
                event_type="diagnosis",
                description=desc,
                timestamp=None,
                citations=[citation]
            ))

        # 6. Procedures
        proc_query = """
            SELECT proc.hadm_id, proc.seq_num, proc.chartdate, proc.icd_code, proc.icd_version, d.long_title
            FROM procedures_icd proc
            LEFT JOIN d_icd_procedures d ON proc.icd_code = d.icd_code AND proc.icd_version = d.icd_version
            WHERE proc.subject_id = ?
        """
        for row in conn.execute(proc_query, (subject_id,)):
            hadm_id = row["hadm_id"]
            seq_num = row["seq_num"]
            chartdate = row["chartdate"]
            title = row["long_title"] or f"Procedure {row['icd_code']}"

            desc = f"Procedure #{seq_num}: {title}"

            citation = Citation(
                table="procedures_icd",
                row_id=f"hadm_id={hadm_id}, seq_num={seq_num}",
                timestamp=chartdate
            )
            events.append(TimelineEvent(
                event_type="procedure",
                description=desc,
                timestamp=chartdate,
                citations=[citation]
            ))

        # 7. ICU Vitals (chartevents)
        # Filter chartevents by subject_id AND whitelisted itemids
        vital_placeholders = ",".join("?" for _ in VITAL_ITEMIDS)
        vital_query = f"""
            SELECT c.subject_id, c.hadm_id, c.stay_id, c.charttime, c.itemid, c.value, c.valuenum, c.valueuom, d.label
            FROM chartevents c
            LEFT JOIN d_items d ON c.itemid = d.itemid
            WHERE c.subject_id = ? AND c.itemid IN ({vital_placeholders})
        """
        params = [subject_id] + VITAL_ITEMIDS
        for row in conn.execute(vital_query, params):
            charttime = row["charttime"]
            itemid = row["itemid"]
            label = row["label"] or f"Vital {itemid}"
            val = row["value"] or (str(row["valuenum"]) if row["valuenum"] is not None else "")
            uom = row["valueuom"] or ""

            val_str = f"{val} {uom}".strip()
            desc = f"Vital Sign: {label} = {val_str}"

            citation = Citation(
                table="chartevents",
                row_id=f"subject_id={subject_id}, charttime={charttime}, itemid={itemid}",
                timestamp=charttime
            )
            events.append(TimelineEvent(
                event_type="vital",
                description=desc,
                timestamp=charttime,
                citations=[citation]
            ))

        # Separate dated and undated events
        dated_events: List[TimelineEvent] = []
        undated_events: List[TimelineEvent] = []

        for e in events:
            if e.timestamp is not None:
                dated_events.append(e)
            else:
                undated_events.append(e)

        # Chronological sort for dated events
        dated_events.sort(key=lambda x: str(x.timestamp))

        return {
            "timeline_events": dated_events,
            "undated_events": undated_events
        }

    finally:
        if close_conn and conn:
            conn.close()
