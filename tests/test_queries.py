"""
tests/test_queries.py
======================
Tests for app/queries.py (all 7 question functions in QUESTION_REGISTRY).

Per DEVELOPMENT.md Section 6:
- For each question in QUESTION_REGISTRY:
  - Test a "data exists" case.
  - Test an "insufficient evidence" case (e.g. non-existent patient ID 99999999).
"""

import sys
from pathlib import Path

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from app.db import get_db_connection
from app.queries import QUESTION_REGISTRY

DB_PATH = PROJECT_ROOT / "data" / "mimic.db"
skip_if_no_db = pytest.mark.skipif(not DB_PATH.exists(), reason="data/mimic.db not found")

REAL_SUBJECT_ID = 10004235
NON_EXISTENT_SUBJECT_ID = 99999999


@pytest.fixture
def conn():
    connection = get_db_connection()
    yield connection
    connection.close()


@skip_if_no_db
def test_question_registry_has_all_7_questions():
    """Registry must contain all 7 required questions from API.md Section 3."""
    expected_qids = {
        "icu_labs", "meds_by_admission", "admission_count",
        "diagnoses_list", "ever_in_icu", "procedures_list", "los_summary"
    }
    assert set(QUESTION_REGISTRY.keys()) == expected_qids


@skip_if_no_db
@pytest.mark.parametrize("qid", list(QUESTION_REGISTRY.keys()))
def test_queries_data_exists_path(conn, qid):
    """Testing question execution against a real patient record."""
    q_func = QUESTION_REGISTRY[qid]["func"]
    res = q_func(REAL_SUBJECT_ID, conn)

    assert res.question_id == qid
    # For subject 10004235, we populated sample records for all categories in data/raw
    assert res.insufficient_evidence is False, f"Question {qid} unexpectedly returned insufficient evidence"
    assert res.rows, f"Question {qid} returned no rows"
    assert res.citations, f"Question {qid} returned no citations"


@skip_if_no_db
@pytest.mark.parametrize("qid", list(QUESTION_REGISTRY.keys()))
def test_queries_insufficient_evidence_path(conn, qid):
    """Testing question execution against non-existent patient returns insufficient_evidence=True."""
    q_func = QUESTION_REGISTRY[qid]["func"]
    res = q_func(NON_EXISTENT_SUBJECT_ID, conn)

    assert res.question_id == qid
    assert res.insufficient_evidence is True, f"Question {qid} failed to return insufficient_evidence=True for empty patient"
    assert res.rows == []
    assert res.citations == []
    assert res.answer_text
