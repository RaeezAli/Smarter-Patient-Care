"""
tests/test_timeline.py
=======================
Tests for app/timeline.py (get_patient_timeline).

Per DEVELOPMENT.md Section 6:
- Run get_patient_timeline() against real subject_ids from loaded data (10004235, 10001401).
- Assert returned dated events are time-sorted.
- Assert every event has at least one citation attached.
"""

import sys
from pathlib import Path

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from app.db import get_db_connection
from app.timeline import get_patient_timeline

DB_PATH = PROJECT_ROOT / "data" / "mimic.db"
skip_if_no_db = pytest.mark.skipif(not DB_PATH.exists(), reason="data/mimic.db not found")

# Subject IDs present in loaded dataset
REAL_SUBJECT_IDS = [10004235, 10001401]


@skip_if_no_db
def test_timeline_structure():
    """get_patient_timeline must return a dict with timeline_events and undated_events keys."""
    res = get_patient_timeline(10004235)
    assert isinstance(res, dict)
    assert "timeline_events" in res
    assert "undated_events" in res


@skip_if_no_db
@pytest.mark.parametrize("subj_id", REAL_SUBJECT_IDS)
def test_timeline_events_time_sorted(subj_id):
    """Timeline events must be chronologically sorted by timestamp."""
    res = get_patient_timeline(subj_id)
    dated_events = res["timeline_events"]
    
    timestamps = [e.timestamp for e in dated_events if e.timestamp is not None]
    assert timestamps == sorted(timestamps), f"Events for patient {subj_id} are not chronologically sorted!"


@skip_if_no_db
@pytest.mark.parametrize("subj_id", REAL_SUBJECT_IDS)
def test_every_event_has_citation(subj_id):
    """Every single returned event (dated and undated) must have at least one Citation."""
    res = get_patient_timeline(subj_id)
    all_events = res["timeline_events"] + res["undated_events"]

    for event in all_events:
        assert event.citations, f"Event '{event.description}' is missing citations!"
        for cit in event.citations:
            assert cit.table, "Citation is missing table field"
            assert cit.row_id, "Citation is missing row_id field"


@skip_if_no_db
def test_nonexistent_patient_returns_empty_timeline():
    """Querying a non-existent patient returns empty event lists without throwing an error."""
    res = get_patient_timeline(99999999)
    assert res["timeline_events"] == []
    assert res["undated_events"] == []
