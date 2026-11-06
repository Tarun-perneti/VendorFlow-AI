"""
test_backend.py - Quick validation test for all Phase 2 backend modules.

Run from the vendorflow/ directory:
    venv/Scripts/python.exe -m tests.test_backend

Tests:
1. Pydantic models - creation and validation
2. Database - init, insert, query
3. Validators - completeness, tax ID, fuzzy matching
4. Decision engine - all four scenarios
5. Email drafts - template fallback
"""

import sys
import os

# Add parent directory to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import (
    VendorSubmission,
    ExtractedDocInfo,
    CheckResult,
    WorkflowDecision,
    mask_account_number,
)
from core.database import (
    init_database,
    create_submission,
    get_submission,
    get_all_submissions,
    get_submission_stats,
    update_submission_status,
    save_check_results,
    get_checks_for_submission,
    DB_PATH,
)
from core.validators import (
    check_completeness,
    validate_tax_id_format,
    validate_country,
    check_company_name_vs_bank_holder,
    SUPPORTED_COUNTRIES,
)
from core.decision import make_decision
from core.email_draft import _generate_template_email


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_result(test_name: str, passed: bool, detail: str = ""):
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {status}  {test_name}")
    if detail and not passed:
        print(f"         → {detail}")


def test_models():
    """Test that Pydantic models create and validate correctly."""
    print_header("TEST 1: Pydantic Models")

    # Test VendorSubmission creation
    sub = VendorSubmission(
        company_name="Acme Corp Pvt Ltd",
        registration_number="U12345MH2020PTC123456",
        country="India",
        tax_id="29ABCDE1234F1Z5",
        bank_account_holder="Acme Corp Private Limited",
        bank_account_number="1234567890123456",
        uploaded_documents=["doc1.pdf", "doc2.pdf"],
    )
    print_result("VendorSubmission creation", sub.company_name == "Acme Corp Pvt Ltd")

    # Test mask_account_number
    masked = mask_account_number("1234567890123456")
    print_result("Account masking", masked == "************3456", f"Got: {masked}")

    masked_short = mask_account_number("123")
    print_result("Short account masking", masked_short == "****", f"Got: {masked_short}")

    # Test CheckResult
    check = CheckResult(
        check_name="test_check",
        passed=True,
        severity="info",
        message="Test passed",
    )
    print_result("CheckResult creation", check.passed == True)

    # Test ExtractedDocInfo with defaults
    doc_info = ExtractedDocInfo(source_file="test.pdf")
    print_result("ExtractedDocInfo defaults", doc_info.doc_type is None)

    # Test model_dump (serialization)
    data = sub.model_dump()
    print_result("model_dump works", isinstance(data, dict) and "company_name" in data)


def test_database():
    """Test database initialization, insert, and query."""
    print_header("TEST 2: Database Operations")

    # Clean up any previous test database
    if DB_PATH.exists():
        DB_PATH.unlink()

    # Initialize
    init_database()
    print_result("Database initialized", DB_PATH.exists())

    # Create a submission
    sub = VendorSubmission(
        company_name="Test Company Ltd",
        registration_number="REG123",
        country="India",
        tax_id="29ABCDE1234F1Z5",
        bank_account_holder="Test Company Ltd",
        bank_account_number="9876543210",
    )
    sub_id = create_submission(sub)
    print_result("Submission created", len(sub_id) > 0, f"ID: {sub_id}")

    # Retrieve it
    record = get_submission(sub_id)
    print_result("Submission retrieved", record is not None)
    print_result(
        "Bank account is masked",
        record["bank_account_masked"] == "******3210",
        f"Got: {record['bank_account_masked']}",
    )
    print_result("Status is PROCESSING", record["status"] == "PROCESSING")

    # Update status
    update_submission_status(sub_id, "APPROVED", "All checks passed")
    record = get_submission(sub_id)
    print_result("Status updated to APPROVED", record["status"] == "APPROVED")

    # Save and retrieve checks
    checks = [
        CheckResult(check_name="test_1", passed=True, severity="info", message="OK"),
        CheckResult(check_name="test_2", passed=False, severity="warning", message="Issue"),
    ]
    save_check_results(sub_id, checks)
    stored_checks = get_checks_for_submission(sub_id)
    print_result("Checks saved and retrieved", len(stored_checks) == 2)

    # Stats
    stats = get_submission_stats()
    print_result("Stats work", stats["total"] == 1 and stats["approved"] == 1)

    # Get all
    all_subs = get_all_submissions()
    print_result("Get all submissions", len(all_subs) >= 1)


def test_validators():
    """Test all validation functions."""
    print_header("TEST 3: Validators")

    # --- Completeness checks ---
    complete_sub = VendorSubmission(
        company_name="Acme Corp",
        registration_number="REG123",
        country="India",
        tax_id="29ABCDE1234F1Z5",
        bank_account_holder="Acme Corp",
        bank_account_number="1234567890",
        uploaded_documents=["doc.pdf"],
    )
    results = check_completeness(complete_sub)
    all_passed = all(r.passed for r in results)
    print_result("Complete submission → all checks pass", all_passed)

    incomplete_sub = VendorSubmission(
        company_name="",
        country="",
        tax_id="",
    )
    results = check_completeness(incomplete_sub)
    critical_fails = [r for r in results if not r.passed and r.severity == "critical"]
    print_result(
        "Incomplete submission → critical failures",
        len(critical_fails) >= 3,
        f"Got {len(critical_fails)} critical failures",
    )

    # --- Tax ID format ---
    # Valid Indian GSTIN
    result = validate_tax_id_format("India", "29ABCDE1234F1Z5")
    print_result("Valid GSTIN → passes", result.passed)

    # Invalid format
    result = validate_tax_id_format("India", "INVALID123")
    print_result("Invalid GSTIN → fails", not result.passed)

    # Valid US EIN
    result = validate_tax_id_format("United States", "12-3456789")
    print_result("Valid EIN → passes", result.passed)

    # Valid UK VAT
    result = validate_tax_id_format("United Kingdom", "GB123456789")
    print_result("Valid UK VAT → passes", result.passed)

    # Valid German VAT
    result = validate_tax_id_format("Germany", "DE123456789")
    print_result("Valid DE VAT → passes", result.passed)

    # Unsupported country
    result = validate_tax_id_format("Antarctica", "TAX123")
    print_result("Unsupported country → warning", result.severity == "warning")

    # --- Country validation ---
    result = validate_country("India")
    print_result("India is supported", result.passed)

    result = validate_country("Mars")
    print_result("Mars is not supported", not result.passed)

    # --- Name matching ---
    # Close match
    result = check_company_name_vs_bank_holder("Acme Corp Pvt Ltd", "Acme Corp Private Limited")
    print_result(
        "Similar names → match",
        result.passed,
        f"Message: {result.message}",
    )

    # Clear mismatch
    result = check_company_name_vs_bank_holder("Acme Corp", "Beta Industries")
    print_result("Different names → mismatch", not result.passed)

    # Exact match
    result = check_company_name_vs_bank_holder("Acme Corp", "Acme Corp")
    print_result("Exact names → match", result.passed)


def test_decision_engine():
    """Test the four core scenarios."""
    print_header("TEST 4: Decision Engine — Four Scenarios")

    # Scenario 1: Complete and consistent → APPROVED
    checks_1 = [
        CheckResult(check_name="company_name_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="country_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="documents_uploaded", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_format", passed=True, severity="critical", message="Format valid"),
        CheckResult(check_name="company_vs_bank_holder", passed=True, severity="critical", message="Names match"),
        CheckResult(check_name="bank_holder_present", passed=True, severity="warning", message="OK"),
    ]
    decision = make_decision("Acme Corp", checks_1)
    print_result(
        "Scenario 1 (perfect) → APPROVED",
        decision.status == "APPROVED",
        f"Got: {decision.status}",
    )

    # Scenario 2: Missing tax document → PENDING
    checks_2 = [
        CheckResult(check_name="company_name_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="country_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="documents_uploaded", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_format", passed=True, severity="critical", message="Format valid"),
        CheckResult(check_name="company_vs_bank_holder", passed=True, severity="critical", message="Match"),
        CheckResult(check_name="has_tax_doc", passed=False, severity="warning",
                    message="No tax certificate document was identified. Missing tax document."),
    ]
    decision = make_decision("Acme Corp", checks_2, extraction_errors=["Could not read tax_doc.pdf"])
    print_result(
        "Scenario 2 (missing tax doc) → PENDING",
        decision.status == "PENDING",
        f"Got: {decision.status}",
    )

    # Scenario 3: Name mismatch → PENDING
    checks_3 = [
        CheckResult(check_name="company_name_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="country_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="documents_uploaded", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_format", passed=True, severity="critical", message="Format valid"),
        CheckResult(check_name="company_vs_bank_holder", passed=False, severity="critical",
                    message="Company name 'Acme Corp' does NOT closely match bank holder 'Acme Industries'"),
    ]
    decision = make_decision("Acme Corp", checks_3)
    print_result(
        "Scenario 3 (name mismatch) → PENDING",
        decision.status == "PENDING",
        f"Got: {decision.status}",
    )

    # Scenario 4: Invalid tax ID → REJECTED
    checks_4 = [
        CheckResult(check_name="company_name_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="country_present", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_present", passed=True, severity="critical", message="Tax ID provided"),
        CheckResult(check_name="documents_uploaded", passed=True, severity="critical", message="OK"),
        CheckResult(check_name="tax_id_format", passed=False, severity="critical",
                    message="Tax ID 'INVALID123' does NOT match the expected GSTIN format for India"),
        CheckResult(check_name="company_vs_bank_holder", passed=True, severity="critical", message="Match"),
    ]
    decision = make_decision("Acme Corp", checks_4)
    print_result(
        "Scenario 4 (invalid tax ID) → REJECTED",
        decision.status == "REJECTED",
        f"Got: {decision.status}",
    )

    # Bonus: Blocked company → REJECTED
    decision = make_decision("Scam Corp", checks_1)
    print_result(
        "Blocked company → REJECTED",
        decision.status == "REJECTED",
        f"Got: {decision.status}",
    )


def test_email_drafts():
    """Test that email templates generate properly."""
    print_header("TEST 5: Email Drafts (template fallback)")

    # Approved email
    decision = WorkflowDecision(
        status="APPROVED",
        explanation="All checks passed.",
        next_actions=["Add vendor to system."],
    )
    email = _generate_template_email("Acme Corp", decision)
    print_result("Approved email generated", "APPROVED" in email and "Acme Corp" in email)

    # Pending email
    decision = WorkflowDecision(
        status="PENDING",
        explanation="Missing info.",
        missing_info=["Tax document required"],
        next_actions=["Upload tax certificate."],
    )
    email = _generate_template_email("Beta Inc", decision)
    print_result("Pending email generated", "PENDING" in email and "Beta Inc" in email)

    # Rejected email
    decision = WorkflowDecision(
        status="REJECTED",
        explanation="Invalid tax ID format.",
        next_actions=["Fix tax ID and resubmit."],
    )
    email = _generate_template_email("Gamma Ltd", decision)
    print_result("Rejected email generated", "unable to approve" in email.lower())


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("\n🧪 VendorFlow AI — Phase 2 Backend Tests")
    print("=" * 60)

    passed = 0
    failed = 0

    try:
        test_models()
        test_database()
        test_validators()
        test_decision_engine()
        test_email_drafts()
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback
        traceback.print_exc()
        failed += 1

    print(f"\n{'='*60}")
    print(f"  All tests completed!")
    print(f"{'='*60}\n")
