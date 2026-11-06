"""
test_workflow.py - Test the complete LangGraph workflow end-to-end.

Run from the vendorflow/ directory:
    venv/Scripts/python.exe -m tests.test_workflow
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import VendorSubmission
from core.database import init_database, DB_PATH
from workflow.graph import run_workflow


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def run_test(scenario_name, submission_dict, expected_status):
    """Run a single workflow test and check the result."""
    print(f"\n  --- {scenario_name} ---")

    from core.database import create_submission
    sub = VendorSubmission(**submission_dict)
    sub_id = create_submission(sub)

    result = run_workflow(submission_dict, sub_id)

    # Print the stage log
    for line in result.get("stage_log", []):
        print(f"    {line}")

    actual_status = result.get("decision", {}).get("status", "UNKNOWN")
    passed = actual_status == expected_status
    icon = "PASS" if passed else "FAIL"
    print(f"\n    [{icon}] Expected: {expected_status}, Got: {actual_status}")

    if not passed:
        explanation = result.get("decision", {}).get("explanation", "")
        print(f"    Explanation: {explanation}")

    return passed


if __name__ == "__main__":
    print_header("LangGraph Workflow Integration Test")

    # Reset database
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_database()

    results = []

    # Scenario 1: Complete and consistent
    results.append(run_test(
        "Scenario 1: Perfect submission -> APPROVED",
        {
            "company_name": "Acme Corp Pvt Ltd",
            "registration_number": "U12345MH2020PTC123456",
            "country": "India",
            "tax_id": "29ABCDE1234F1Z5",
            "bank_account_holder": "Acme Corp Pvt Ltd",
            "bank_account_number": "1234567890123456",
            "uploaded_documents": [],  # No real files for this test
        },
        "PENDING",  # No docs uploaded, so can't be APPROVED
    ))

    # Scenario 2: Missing critical fields
    results.append(run_test(
        "Scenario 2: Missing tax ID -> PENDING",
        {
            "company_name": "Beta Industries",
            "registration_number": "",
            "country": "India",
            "tax_id": "",
            "bank_account_holder": "Beta Industries",
            "bank_account_number": "9876543210",
            "uploaded_documents": [],
        },
        "PENDING",
    ))

    # Scenario 3: Name mismatch
    results.append(run_test(
        "Scenario 3: Name mismatch -> PENDING",
        {
            "company_name": "Acme Corp Ltd",
            "registration_number": "REG123",
            "country": "United States",
            "tax_id": "12-3456789",
            "bank_account_holder": "Totally Different Company",
            "bank_account_number": "1234567890",
            "uploaded_documents": [],
        },
        "PENDING",
    ))

    # Scenario 4: Invalid tax ID format
    results.append(run_test(
        "Scenario 4: Invalid tax ID -> REJECTED",
        {
            "company_name": "Gamma Trading",
            "registration_number": "REG999",
            "country": "India",
            "tax_id": "INVALID_TAX_123",
            "bank_account_holder": "Gamma Trading",
            "bank_account_number": "5555666677778888",
            "uploaded_documents": [],
        },
        "REJECTED",
    ))

    # Summary
    print_header("Summary")
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"  {passed}/{total} scenarios passed")
    if passed == total:
        print("  All workflow tests PASSED!")
    else:
        print("  Some tests FAILED - review output above.")

