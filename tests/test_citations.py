"""
tests/test_citations.py
========================
Tests for app/citations.py dataclasses.

Per DEVELOPMENT.md Section 6:
- Assert that TimelineEvent cannot be constructed without at least one Citation.
- Assert QueryResult holds citations correctly for both evidence and insufficient_evidence cases.
"""

import sys
from pathlib import Path

# Ensure project root is in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from app.citations import Citation, TimelineEvent, QueryResult


def test_timeline_event_requires_citation():
    """TimelineEvent must raise ValueError if constructed without citations."""
    with pytest.raises(ValueError, match="TimelineEvent cannot be constructed without at least one Citation"):
        TimelineEvent(
            event_type="admission",
            description="Test Admission",
            timestamp="2196-01-14 15:15:00",
            citations=[]
        )


def test_timeline_event_valid():
    """TimelineEvent constructs cleanly when valid citations are passed."""
    cit = Citation(table="admissions", row_id="hadm_id=123", timestamp="2196-01-14 15:15:00")
    event = TimelineEvent(
        event_type="admission",
        description="Test Admission",
        timestamp="2196-01-14 15:15:00",
        citations=[cit]
    )
    assert event.citations == [cit]


def test_query_result_insufficient_evidence():
    """QueryResult with insufficient_evidence=True holds empty citations by design."""
    res = QueryResult(
        question_id="icu_labs",
        answer_text="No supporting records found.",
        rows=[],
        citations=[],
        insufficient_evidence=True
    )
    assert res.insufficient_evidence is True
    assert res.citations == []
