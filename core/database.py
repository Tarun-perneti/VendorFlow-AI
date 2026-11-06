"""
database.py — SQLite operations for VendorFlow AI

Handles all database interactions: creating tables, inserting submissions,
updating statuses, saving validation checks, and querying history.

Why SQLite?
- Zero setup: it's just a file, no server needed.
- Built into Python: no extra dependencies.
- Perfect for a demo/interview: easy to deploy anywhere.
- Data persists across app restarts.

Why a separate file?
- All SQL is in one place, not scattered across the app.
- Easy to test and debug database operations independently.
"""

import sqlite3
import uuid
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.models import (
    VendorSubmission,
    SubmissionRecord,
    CheckResult,
    ExtractedDocInfo,
    WorkflowDecision,
    mask_account_number,
)

# Database file location — stored in the data/ directory
DB_PATH = Path(__file__).parent.parent / "data" / "vendorflow.db"


def get_connection() -> sqlite3.Connection:
    """
    Get a database connection. Creates the data directory if needed.
    
    row_factory = sqlite3.Row lets us access columns by name
    instead of index, making code more readable:
        row["company_name"] instead of row[1]
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # better concurrent access
    conn.execute("PRAGMA foreign_keys=ON")   # enforce foreign key constraints
    return conn


def init_database():
    """
    Create all tables if they don't exist.
    Called once when the app starts.
    
    Safe to call multiple times — IF NOT EXISTS prevents errors.
    """
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS submissions (
                id                  TEXT PRIMARY KEY,
                company_name        TEXT NOT NULL,
                registration_number TEXT DEFAULT '',
                country             TEXT DEFAULT '',
                tax_id              TEXT DEFAULT '',
                bank_account_holder TEXT DEFAULT '',
                bank_account_masked TEXT DEFAULT '',
                status              TEXT DEFAULT 'PROCESSING',
                decision_explanation TEXT,
                email_draft         TEXT,
                submitted_at        TEXT NOT NULL,
                completed_at        TEXT
            );

            CREATE TABLE IF NOT EXISTS documents (
                id              TEXT PRIMARY KEY,
                submission_id   TEXT NOT NULL,
                filename        TEXT NOT NULL,
                file_path       TEXT NOT NULL,
                doc_type        TEXT,
                extracted_text  TEXT,
                extracted_data  TEXT,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            );

            CREATE TABLE IF NOT EXISTS validation_checks (
                id              TEXT PRIMARY KEY,
                submission_id   TEXT NOT NULL,
                check_name      TEXT NOT NULL,
                passed          INTEGER NOT NULL,
                severity        TEXT NOT NULL,
                message         TEXT,
                checked_at      TEXT NOT NULL,
                FOREIGN KEY (submission_id) REFERENCES submissions(id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Submission CRUD operations
# ---------------------------------------------------------------------------

def create_submission(submission: VendorSubmission) -> str:
    """
    Save a new vendor submission to the database.
    
    Returns the generated submission ID (UUID).
    
    Important: We mask the bank account number BEFORE storing it.
    The full account number is never written to the database.
    """
    submission_id = str(uuid.uuid4())
    masked_account = mask_account_number(submission.bank_account_number)
    now = datetime.now().isoformat()

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO submissions 
            (id, company_name, registration_number, country, tax_id,
             bank_account_holder, bank_account_masked, status, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSING', ?)
            """,
            (
                submission_id,
                submission.company_name,
                submission.registration_number,
                submission.country,
                submission.tax_id,
                submission.bank_account_holder,
                masked_account,
                now,
            ),
        )
        conn.commit()
        return submission_id
    finally:
        conn.close()


def update_submission_status(
    submission_id: str,
    status: str,
    explanation: str = "",
    email_draft: str = "",
):
    """
    Update the final status of a submission after the workflow completes.
    Also sets the completed_at timestamp.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            UPDATE submissions 
            SET status = ?, decision_explanation = ?, email_draft = ?, 
                completed_at = ?
            WHERE id = ?
            """,
            (status, explanation, email_draft, datetime.now().isoformat(), submission_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_submission(submission_id: str) -> dict | None:
    """
    Retrieve a single submission by ID.
    Returns a dict with all fields, or None if not found.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM submissions WHERE id = ?", (submission_id,)
        ).fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        conn.close()


def get_all_submissions() -> list[dict]:
    """
    Get all submissions, ordered by most recent first.
    Used by the dashboard page.
    """
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM submissions ORDER BY submitted_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_submission_stats() -> dict:
    """
    Get aggregate statistics for the dashboard.
    Returns counts of total, approved, pending, and rejected submissions.
    """
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'APPROVED'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'PENDING'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'REJECTED'"
        ).fetchone()[0]
        processing = conn.execute(
            "SELECT COUNT(*) FROM submissions WHERE status = 'PROCESSING'"
        ).fetchone()[0]

        return {
            "total": total,
            "approved": approved,
            "pending": pending,
            "rejected": rejected,
            "processing": processing,
            "approval_rate": round(approved / total * 100, 1) if total > 0 else 0,
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Document operations
# ---------------------------------------------------------------------------

def save_document(
    submission_id: str,
    filename: str,
    file_path: str,
    doc_type: str = "",
    extracted_text: str = "",
    extracted_data: dict | None = None,
):
    """
    Save a document record linked to a submission.
    extracted_data is stored as a JSON string.
    """
    doc_id = str(uuid.uuid4())
    data_json = json.dumps(extracted_data) if extracted_data else ""

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO documents 
            (id, submission_id, filename, file_path, doc_type, 
             extracted_text, extracted_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (doc_id, submission_id, filename, file_path, doc_type,
             extracted_text, data_json),
        )
        conn.commit()
    finally:
        conn.close()


def get_documents_for_submission(submission_id: str) -> list[dict]:
    """Get all documents for a given submission."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM documents WHERE submission_id = ?", (submission_id,)
        ).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            # Parse the JSON extracted_data back into a dict
            if d.get("extracted_data"):
                try:
                    d["extracted_data"] = json.loads(d["extracted_data"])
                except json.JSONDecodeError:
                    d["extracted_data"] = {}
            results.append(d)
        return results
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Validation check operations
# ---------------------------------------------------------------------------

def save_check_result(submission_id: str, check: CheckResult):
    """Save a single validation check result."""
    check_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO validation_checks 
            (id, submission_id, check_name, passed, severity, message, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                check_id,
                submission_id,
                check.check_name,
                1 if check.passed else 0,
                check.severity,
                check.message,
                datetime.now().isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def save_check_results(submission_id: str, checks: list[CheckResult]):
    """Save multiple validation check results at once."""
    conn = get_connection()
    try:
        for check in checks:
            check_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO validation_checks 
                (id, submission_id, check_name, passed, severity, message, checked_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    check_id,
                    submission_id,
                    check.check_name,
                    1 if check.passed else 0,
                    check.severity,
                    check.message,
                    datetime.now().isoformat(),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def get_checks_for_submission(submission_id: str) -> list[dict]:
    """Get all validation checks for a given submission."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM validation_checks WHERE submission_id = ? ORDER BY checked_at",
            (submission_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
