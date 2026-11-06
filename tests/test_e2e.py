"""
test_e2e.py - End-to-end test of all 4 scenarios with actual PDF documents.

Run from the vendorflow/ directory:
    venv/Scripts/python.exe -m tests.test_e2e

This test uses the sample PDFs created by generate_sample_docs.py.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from core.models import VendorSubmission
from core.database import init_database, create_submission, get_submission, DB_PATH
from workflow.graph import run_workflow

SAMPLE_DIR = Path(__file__).parent / "sample_docs"


def print_header(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")


def run_scenario(name, submission_data, expected_status):
    """Run a single scenario and report results."""
    print(f"\n  {'─'*60}")
    print(f"  {name}")
    print(f"  {'─'*60}")

    sub = VendorSubmission(**submission_data)
    sub_id = create_submission(sub)
    result = run_workflow(submission_data, sub_id)

    # Print log
    for line in result.get("stage_log", []):
        print(f"    {line}")

    actual = result.get("decision", {}).get("status", "UNKNOWN")
    explanation = result.get("decision", {}).get("explanation", "")
    passed = actual == expected_status

    print(f"\n    Expected: {expected_status}")
    print(f"    Actual:   {actual}")
    print(f"    Result:   {'PASS' if passed else 'FAIL'}")

    if not passed:
        print(f"    Explanation: {explanation}")

    return passed


if __name__ == "__main__":
    print_header("VendorFlow AI - End-to-End Test Suite")

    # Ensure sample docs exist
    if not (SAMPLE_DIR / "registration_certificate.pdf").exists():
        print("  Generating sample documents first...")
        from tests.generate_sample_docs import (
            create_registration_certificate,
            create_tax_certificate,
            create_bank_statement,
            create_mismatched_bank_statement,
        )
        create_registration_certificate()
        create_tax_certificate()
        create_bank_statement()
        create_mismatched_bank_statement()

    # Reset database
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_database()

    reg_cert = str(SAMPLE_DIR / "registration_certificate.pdf")
    tax_cert = str(SAMPLE_DIR / "tax_certificate.pdf")
    bank_stmt = str(SAMPLE_DIR / "bank_statement.pdf")
    bank_mismatch = str(SAMPLE_DIR / "bank_statement_mismatch.pdf")

    results = []

    # -----------------------------------------------------------------------
    # Scenario 1: Complete and consistent -> APPROVED
    # -----------------------------------------------------------------------
    results.append(run_scenario(
        "Scenario 1: Complete submission with matching documents -> APPROVED",
        {
            "company_name": "Acme Corp Pvt Ltd",
            "registration_number": "U12345MH2020PTC123456",
            "country": "India",
            "tax_id": "29ABCDE1234F1Z5",
            "bank_account_holder": "Acme Corp Pvt Ltd",
            "bank_account_number": "1234567890123456",
            "uploaded_documents": [reg_cert, tax_cert, bank_stmt],
        },
        "APPROVED",
    ))

    # -----------------------------------------------------------------------
    # Scenario 2: Missing tax document -> PENDING
    # -----------------------------------------------------------------------
    results.append(run_scenario(
        "Scenario 2: Missing tax certificate document -> PENDING",
        {
            "company_name": "Beta Industries Ltd",
            "registration_number": "U98765DL2021PTC654321",
            "country": "India",
            "tax_id": "07FGHIJ5678K2Z3",
            "bank_account_holder": "Beta Industries Ltd",
            "bank_account_number": "9876543210",
            "uploaded_documents": [reg_cert],  # Only registration, no tax doc
        },
        "PENDING",
    ))

    # -----------------------------------------------------------------------
    # Scenario 3: Company name vs bank holder mismatch -> PENDING
    # -----------------------------------------------------------------------
    results.append(run_scenario(
        "Scenario 3: Name mismatch between company and bank holder -> PENDING",
        {
            "company_name": "Acme Corp Pvt Ltd",
            "registration_number": "U12345MH2020PTC123456",
            "country": "India",
            "tax_id": "29ABCDE1234F1Z5",
            "bank_account_holder": "Totally Different Industries LLC",
            "bank_account_number": "5555666677778888",
            "uploaded_documents": [reg_cert, tax_cert],
        },
        "PENDING",
    ))

    # -----------------------------------------------------------------------
    # Scenario 4: Invalid tax ID format -> REJECTED
    # -----------------------------------------------------------------------
    results.append(run_scenario(
        "Scenario 4: Invalid GSTIN format -> REJECTED",
        {
            "company_name": "Gamma Trading Co",
            "registration_number": "REG999",
            "country": "India",
            "tax_id": "INVALID_FORMAT_XYZ",
            "bank_account_holder": "Gamma Trading Co",
            "bank_account_number": "1111222233334444",
            "uploaded_documents": [reg_cert],
        },
        "REJECTED",
    ))

    # -----------------------------------------------------------------------
    # Summary
    # -----------------------------------------------------------------------
    print_header("Test Summary")
    passed_count = sum(1 for r in results if r)
    total_count = len(results)
    print(f"  Passed: {passed_count}/{total_count}")

    for i, r in enumerate(results, 1):
        icon = "PASS" if r else "FAIL"
        print(f"    Scenario {i}: [{icon}]")

    if passed_count == total_count:
        print(f"\n  All {total_count} scenarios PASSED!")
    else:
        print(f"\n  {total_count - passed_count} scenario(s) FAILED.")

