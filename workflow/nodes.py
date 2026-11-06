"""
nodes.py — Individual workflow nodes for the LangGraph pipeline

Each function here is a "node" — a step in the workflow.
Every node:
1. Receives the current state (VendorWorkflowState).
2. Does some work (extract text, validate, decide, etc.).
3. Returns a dict with only the keys it wants to update.

LangGraph automatically merges the returned dict into the shared state.

Why separate functions (not a big class)?
- Each node is independently testable.
- Easy to explain: "this node does X, that node does Y."
- Easy to add/remove/reorder nodes.
"""

from core.models import (
    VendorSubmission,
    ExtractedDocInfo,
    CheckResult,
    WorkflowDecision,
)
from core.document import process_uploaded_document
from core.validators import (
    check_completeness,
    validate_tax_id_format,
    validate_country,
    check_company_name_vs_bank_holder,
    check_company_name_vs_document,
    check_tax_id_vs_document,
    check_required_document_types,
)
from core.decision import make_decision
from core.email_draft import generate_email_draft
from core.database import (
    save_document,
    save_check_results,
    update_submission_status,
)
from workflow.state import VendorWorkflowState


# ---------------------------------------------------------------------------
# Node 1: Extract Documents
# ---------------------------------------------------------------------------
def extract_documents(state: VendorWorkflowState) -> dict:
    """
    Process each uploaded PDF:
    1. Extract text using pdfplumber.
    2. Classify the document type (LLM or keyword fallback).
    3. Extract structured fields (company name, tax ID, etc.).
    
    Updates state with:
    - extracted_docs: list of ExtractedDocInfo dicts
    - extraction_errors: list of error messages
    - stage_log: appends log entries
    """
    submission = VendorSubmission(**state["submission"])
    submission_id = state["submission_id"]
    log = list(state.get("stage_log", []))
    
    log.append("📄 Stage: Document Extraction — starting...")

    extracted_docs = []
    extraction_errors = []

    if not submission.uploaded_documents:
        log.append("  ⚠️ No documents were uploaded.")
    else:
        for file_path in submission.uploaded_documents:
            try:
                log.append(f"  📎 Processing: {file_path.split('/')[-1].split(chr(92))[-1]}")
                doc_info = process_uploaded_document(file_path)
                extracted_docs.append(doc_info.model_dump())

                # Save to database
                save_document(
                    submission_id=submission_id,
                    filename=doc_info.source_file,
                    file_path=file_path,
                    doc_type=doc_info.doc_type or "",
                    extracted_text=doc_info.raw_text,
                    extracted_data=doc_info.model_dump(),
                )

                if doc_info.doc_type and doc_info.doc_type != "unknown":
                    log.append(f"    ✅ Classified as: {doc_info.doc_type}")
                else:
                    log.append(f"    ⚠️ Could not classify document type.")

                if doc_info.extracted_company_name:
                    log.append(f"    📝 Found company name: {doc_info.extracted_company_name}")

            except Exception as e:
                error_msg = f"Failed to process {file_path}: {str(e)}"
                extraction_errors.append(error_msg)
                log.append(f"    ❌ Error: {error_msg}")

    doc_count = len(extracted_docs)
    log.append(f"  ✅ Extraction complete: {doc_count} document(s) processed, "
               f"{len(extraction_errors)} error(s).")

    return {
        "extracted_docs": extracted_docs,
        "extraction_errors": extraction_errors,
        "current_stage": "extract_documents",
        "stage_log": log,
    }


# ---------------------------------------------------------------------------
# Node 2: Validate Completeness
# ---------------------------------------------------------------------------
def validate_completeness(state: VendorWorkflowState) -> dict:
    """
    Check whether all mandatory fields and documents are present.
    
    Runs checks for:
    - Required form fields (company name, country, tax ID, etc.)
    - Required document types (registration cert, tax cert)
    
    Updates state with:
    - completeness_checks: list of CheckResult dicts
    - missing_fields: list of descriptions of what's missing
    """
    submission = VendorSubmission(**state["submission"])
    extracted_docs = [ExtractedDocInfo(**d) for d in state.get("extracted_docs", [])]
    log = list(state.get("stage_log", []))

    log.append("✅ Stage: Completeness Validation — starting...")

    # Run field completeness checks
    checks = check_completeness(submission)

    # Also validate tax ID format here (not just in consistency stage)
    # because an invalid tax ID format is a critical issue that should
    # be caught even if we skip the consistency checks.
    if submission.tax_id.strip() and submission.country.strip():
        tax_format_check = validate_tax_id_format(submission.country, submission.tax_id)
        checks.append(tax_format_check)

    # Run document type checks
    if extracted_docs:
        doc_type_checks = check_required_document_types(extracted_docs)
        checks.extend(doc_type_checks)

    # Identify missing fields
    missing_fields = []
    for check in checks:
        if not check.passed:
            missing_fields.append(check.message)
            log.append(f"  ❌ {check.check_name}: {check.message}")
        else:
            log.append(f"  ✅ {check.check_name}: {check.message}")

    passed_count = sum(1 for c in checks if c.passed)
    total_count = len(checks)
    log.append(f"  📊 Completeness: {passed_count}/{total_count} checks passed.")

    # Save checks to database
    submission_id = state["submission_id"]
    save_check_results(submission_id, checks)

    return {
        "completeness_checks": [c.model_dump() for c in checks],
        "missing_fields": missing_fields,
        "current_stage": "validate_completeness",
        "stage_log": log,
    }


# ---------------------------------------------------------------------------
# Node 3: Verify Consistency
# ---------------------------------------------------------------------------
def verify_consistency(state: VendorWorkflowState) -> dict:
    """
    Cross-check submitted information against extracted document data.
    
    Checks:
    - Company name vs. bank account holder name (fuzzy match).
    - Tax ID format vs. country (regex).
    - Company name vs. document names (fuzzy match).
    - Tax ID vs. document tax IDs (exact match after normalization).
    - Country is in the supported list.
    """
    submission = VendorSubmission(**state["submission"])
    extracted_docs = [ExtractedDocInfo(**d) for d in state.get("extracted_docs", [])]
    log = list(state.get("stage_log", []))

    log.append("🔍 Stage: Consistency Verification — starting...")

    checks = []

    # 1. Company name vs bank account holder
    name_check = check_company_name_vs_bank_holder(
        submission.company_name,
        submission.bank_account_holder,
    )
    checks.append(name_check)
    status_icon = "✅" if name_check.passed else "❌"
    log.append(f"  {status_icon} {name_check.check_name}: {name_check.message}")

    # 2. Country validation
    country_check = validate_country(submission.country)
    checks.append(country_check)
    status_icon = "✅" if country_check.passed else "❌"
    log.append(f"  {status_icon} {country_check.check_name}: {country_check.message}")

    # 4. Cross-check against each extracted document
    for doc_info in extracted_docs:
        # Company name vs document
        doc_name_check = check_company_name_vs_document(
            submission.company_name, doc_info
        )
        checks.append(doc_name_check)
        if doc_name_check.severity != "info":  # Don't log skip messages
            status_icon = "✅" if doc_name_check.passed else "❌"
            log.append(f"  {status_icon} {doc_name_check.check_name}: {doc_name_check.message}")

        # Tax ID vs document
        doc_tax_check = check_tax_id_vs_document(submission.tax_id, doc_info)
        checks.append(doc_tax_check)
        if doc_tax_check.severity != "info":
            status_icon = "✅" if doc_tax_check.passed else "❌"
            log.append(f"  {status_icon} {doc_tax_check.check_name}: {doc_tax_check.message}")

    passed_count = sum(1 for c in checks if c.passed)
    total_count = len(checks)
    log.append(f"  📊 Consistency: {passed_count}/{total_count} checks passed.")

    # Save checks to database
    submission_id = state["submission_id"]
    save_check_results(submission_id, checks)

    return {
        "consistency_checks": [c.model_dump() for c in checks],
        "current_stage": "verify_consistency",
        "stage_log": log,
    }


# ---------------------------------------------------------------------------
# Node 4: Make Decision
# ---------------------------------------------------------------------------
def decide(state: VendorWorkflowState) -> dict:
    """
    Apply the deterministic decision rules.
    
    Collects ALL checks from completeness and consistency stages,
    then uses the rule engine to produce APPROVED / PENDING / REJECTED.
    
    This is the critical node — NO LLM involvement here.
    """
    submission = VendorSubmission(**state["submission"])
    log = list(state.get("stage_log", []))

    log.append("⚖️ Stage: Decision Engine — evaluating rules...")

    # Collect all checks from previous stages
    all_check_dicts = (
        state.get("completeness_checks", [])
        + state.get("consistency_checks", [])
    )
    all_checks = [CheckResult(**c) for c in all_check_dicts]
    extraction_errors = state.get("extraction_errors", [])

    # Run the decision engine
    decision = make_decision(
        company_name=submission.company_name,
        all_checks=all_checks,
        extraction_errors=extraction_errors,
    )

    # Log the result
    status_emoji = {"APPROVED": "✅", "PENDING": "⏳", "REJECTED": "❌"}
    emoji = status_emoji.get(decision.status, "❓")
    log.append(f"  {emoji} Decision: {decision.status}")
    log.append(f"  📝 Explanation: {decision.explanation}")

    if decision.missing_info:
        log.append(f"  📋 Missing information:")
        for item in decision.missing_info:
            log.append(f"     • {item}")

    if decision.next_actions:
        log.append(f"  👉 Next actions:")
        for action in decision.next_actions:
            log.append(f"     • {action}")

    return {
        "decision": decision.model_dump(),
        "current_stage": "decide",
        "stage_log": log,
    }


# ---------------------------------------------------------------------------
# Node 5: Generate Output
# ---------------------------------------------------------------------------
def generate_output(state: VendorWorkflowState) -> dict:
    """
    Final stage: generate the email draft and save everything to the database.
    
    Uses LLM for a polished email (falls back to template if unavailable).
    Updates the submission record with the final status.
    """
    submission = VendorSubmission(**state["submission"])
    decision = WorkflowDecision(**state["decision"])
    submission_id = state["submission_id"]
    log = list(state.get("stage_log", []))

    log.append("📧 Stage: Output Generation — starting...")

    # Generate email draft
    email = generate_email_draft(submission.company_name, decision)
    log.append("  ✅ Email draft generated.")

    # Update the database with final status
    update_submission_status(
        submission_id=submission_id,
        status=decision.status,
        explanation=decision.explanation,
        email_draft=email,
    )
    log.append(f"  ✅ Database updated with status: {decision.status}")
    log.append(f"  🏁 Workflow complete!")

    return {
        "email_draft": email,
        "current_stage": "generate_output",
        "stage_log": log,
    }


# ---------------------------------------------------------------------------
# Router function for conditional edge
# ---------------------------------------------------------------------------
def should_skip_consistency(state: VendorWorkflowState) -> str:
    """
    Conditional routing function.
    
    After completeness validation, check if critical data is missing.
    If so, skip consistency checks (they'd be meaningless) and go
    straight to the decision node.
    
    Returns the name of the next node to execute:
    - "verify_consistency" if we should continue normally.
    - "decide" if we should skip to the decision.
    """
    completeness_checks = state.get("completeness_checks", [])

    # Check for critical failures
    critical_failures = [
        c for c in completeness_checks
        if not c.get("passed", True) and c.get("severity") == "critical"
    ]

    if critical_failures:
        # Critical data missing — skip consistency, go to decision
        return "decide"
    else:
        # All critical fields present — continue to consistency checks
        return "verify_consistency"

