"""
app/citations.py
================
Shared data contracts and citation dataclasses for Smarter Patient Care.

Per API.md Section 4:
- Citation: Source metadata for a single clinical fact/row.
- TimelineEvent: A single event rendered on the patient timeline.
- QueryResult: Structured response returned by functions in queries.py.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


@dataclass
class Citation:
    table: str
    row_id: str          # stringified, may be composite e.g. "hadm_id=123, seq_num=2"
    timestamp: Optional[str]


@dataclass
class TimelineEvent:
    event_type: str       # "admission" | "transfer" | "lab" | "medication" | "diagnosis" | "procedure" | "vital"
    description: str      # human-readable, e.g. "Hemoglobin: 10.2 g/dL (LOW)"
    timestamp: Optional[str]
    citations: List[Citation] = field(default_factory=list)

    def __post_init__(self):
        # Enforce rule that a TimelineEvent must have a non-empty citations list
        if not self.citations:
            raise ValueError("TimelineEvent cannot be constructed without at least one Citation.")


@dataclass
class QueryResult:
    question_id: str
    answer_text: str
    rows: List[Dict[str, Any]]
    citations: List[Citation] = field(default_factory=list)
    insufficient_evidence: bool = False
