"""
app/routes.py
=============
HTTP Route Handlers for Smarter Patient Care.

Per API.md Section 1-2 & 5 and UI_UX.md Section 3:
- GET /                           : Patient picker list (templates/index.html)
- GET /patient/<subject_id>        : Patient timeline view (templates/timeline.html)
- GET /patient/<subject_id>/ask    : Supported questions panel (templates/qa.html)
- POST /patient/<subject_id>/ask   : Submit question and return QueryResult (templates/qa.html)
- GET /about                       : Static safety statement (templates/about.html)
- GET /health                      : JSON health check
"""

import logging
import sqlite3
from flask import Blueprint, request, jsonify, render_template, abort

from app.db import get_db_connection
from app.timeline import get_patient_timeline
from app.queries import QUESTION_REGISTRY

logger = logging.getLogger(__name__)

main_bp = Blueprint("main", __name__)


def check_patient_exists(conn: sqlite3.Connection, subject_id: int) -> bool:
    """Helper to verify subject_id exists in patients table."""
    row = conn.execute(
        "SELECT 1 FROM patients WHERE subject_id = ?", (subject_id,)
    ).fetchone()
    return row is not None


@main_bp.route("/", methods=["GET"])
def index():
    """GET / — Home page / Patient picker."""
    try:
        conn = get_db_connection()
        try:
            patients = conn.execute(
                "SELECT subject_id, gender, anchor_age FROM patients ORDER BY subject_id"
            ).fetchall()
            patient_list = [dict(p) for p in patients]
        finally:
            conn.close()

        return render_template("index.html", patients=patient_list)
    except Exception as exc:
        logger.exception("Error on GET /")
        return render_template("errors.html", status_code=500, error_title="Server Error", error_message="Internal server error occurred."), 500


@main_bp.route("/patient/<int:subject_id>", methods=["GET"])
def patient_timeline(subject_id: int):
    """GET /patient/<subject_id> — Timeline view for one patient."""
    try:
        conn = get_db_connection()
        try:
            if not check_patient_exists(conn, subject_id):
                return render_template("errors.html", status_code=404, error_title="Patient Not Found", error_message=f"No patient with ID {subject_id} exists in this dataset."), 404

            timeline_data = get_patient_timeline(subject_id, conn)
            
            patient = conn.execute(
                "SELECT gender, anchor_age FROM patients WHERE subject_id = ?", (subject_id,)
            ).fetchone()
            patient_summary = dict(patient) if patient else {}
        finally:
            conn.close()

        return render_template(
            "timeline.html",
            subject_id=subject_id,
            patient_summary=patient_summary,
            timeline_events=timeline_data["timeline_events"],
            undated_events=timeline_data["undated_events"]
        )
    except Exception as exc:
        logger.exception(f"Error on GET /patient/{subject_id}")
        return render_template("errors.html", status_code=500, error_title="Server Error", error_message="Internal server error occurred."), 500


@main_bp.route("/patient/<int:subject_id>/ask", methods=["GET"])
def ask_panel(subject_id: int):
    """GET /patient/<subject_id>/ask — Question selection panel."""
    try:
        conn = get_db_connection()
        try:
            if not check_patient_exists(conn, subject_id):
                return render_template("errors.html", status_code=404, error_title="Patient Not Found", error_message=f"No patient with ID {subject_id} exists in this dataset."), 404
        finally:
            conn.close()

        questions = [
            {"question_id": qid, "text": qdata["text"]}
            for qid, qdata in QUESTION_REGISTRY.items()
        ]

        return render_template(
            "qa.html",
            subject_id=subject_id,
            supported_questions=questions,
            result=None
        )
    except Exception as exc:
        logger.exception(f"Error on GET /patient/{subject_id}/ask")
        return render_template("errors.html", status_code=500, error_title="Server Error", error_message="Internal server error occurred."), 500


@main_bp.route("/patient/<int:subject_id>/ask", methods=["POST"])
def submit_question(subject_id: int):
    """POST /patient/<subject_id>/ask — Submit question and return answer + citations."""
    try:
        if request.is_json:
            data = request.get_json() or {}
            qid = data.get("question_id")
        else:
            qid = request.form.get("question_id")

        if not qid or qid not in QUESTION_REGISTRY:
            return render_template(
                "errors.html",
                status_code=400,
                error_title="Invalid Question ID",
                error_message=f"Invalid or missing question_id '{qid}'. Supported questions: {list(QUESTION_REGISTRY.keys())}"
            ), 400

        conn = get_db_connection()
        try:
            if not check_patient_exists(conn, subject_id):
                return render_template("errors.html", status_code=404, error_title="Patient Not Found", error_message=f"No patient with ID {subject_id} exists in this dataset."), 404

            q_func = QUESTION_REGISTRY[qid]["func"]
            result = q_func(subject_id, conn)
        finally:
            conn.close()

        questions = [
            {"question_id": k, "text": v["text"]}
            for k, v in QUESTION_REGISTRY.items()
        ]

        return render_template(
            "qa.html",
            subject_id=subject_id,
            question_id=qid,
            question_text=QUESTION_REGISTRY[qid]["text"],
            supported_questions=questions,
            result=result
        )
    except Exception as exc:
        logger.exception(f"Error on POST /patient/{subject_id}/ask")
        return render_template("errors.html", status_code=500, error_title="Server Error", error_message="Internal server error occurred."), 500


@main_bp.route("/about", methods=["GET"])
def about():
    """GET /about — Static safety statement & methodology page."""
    return render_template("about.html")


@main_bp.route("/health", methods=["GET"])
def health():
    """GET /health — Sanity check for app & DB connection."""
    try:
        conn = get_db_connection()
        try:
            conn.execute("SELECT 1").fetchone()
        finally:
            conn.close()
        return jsonify({"status": "ok"}), 200
    except Exception as exc:
        logger.exception("Health check failed")
        return jsonify({"status": "error", "detail": str(exc)}), 500
