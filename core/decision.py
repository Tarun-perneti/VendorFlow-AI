"""
decision.py — Deterministic decision engine for VendorFlow AI

This is the MOST important module in the system.
It takes all validation check results and produces a final decision:
APPROVED, PENDING, or REJECTED.

Why is this separate from the LLM?
- The decision MUST be deterministic and explainable.
- Given the same inputs, it must always produce the same output.
- You must be able to explain every rule in an interview.
- An LLM could give different answers each time or hallucinate approvals.

Decision Logic:
1. REJECTED if any rejection condition is met.
2. APPROVED if ALL critical checks pass and no missing critical info.
3. PENDING for everything in between.
"""

from core.models import CheckResult, WorkflowDecision


# ---------------------------------------------------------------------------
# Rejection blocklist — for demo purposes
# ---------------------------------------------------------------------------
# In a real system, this would be checked against a sanctions database.
# For the demo, we use a small hardcoded list.
BLOCKED_COMPANIES = [
    "fraudulent enterprises",
    "scam corp",
    "blacklisted trading",
]


def is_company_blocked(company_name: str) -> bool:
    """Check if the company is on the blocklist."""
    return company_name.strip().lower() in BLOCKED_COMPANIES


# ---------------------------------------------------------------------------
# Main Decision Engine
# ---------------------------------------------------------------------------

def make_decision(
    company_name: str,
    all_checks: list[CheckResult],
    extraction_errors: list[str] | None = None,
) -> WorkflowDecision:
    """
    The core decision function. Takes all validation results and produces
    a final verdict.
    
    Decision Rules (evaluated in order):
    
    1. REJECTED if:
       - Company is on the blocklist.
       - Tax ID format is critically invalid (severity=critical, passed=False,
         check_name=tax_id_format).
    
    2. APPROVED if:
       - All critical-severity checks passed.
       - No extraction errors.
    
    3. PENDING otherwise:
       - Some checks failed but not severely enough to reject.
       - Missing information that needs human review.
    
    Args:
        company_name: The submitted company name.
        all_checks: All CheckResult objects from completeness + consistency stages.
        extraction_errors: Any errors from the document extraction stage.
    
    Returns:
        WorkflowDecision with status, explanation, and next actions.
    """
    if extraction_errors is None:
        extraction_errors = []

    # Separate passed and failed checks
    passed_checks = [c for c in all_checks if c.passed]
    failed_checks = [c for c in all_checks if not c.passed]

    # Get critical failures specifically
    critical_failures = [c for c in failed_checks if c.severity == "critical"]
    warning_failures = [c for c in failed_checks if c.severity == "warning"]

    # Build the missing info list
    missing_info = []
    for check in failed_checks:
        if "missing" in check.message.lower() or "not provided" in check.message.lower():
            missing_info.append(check.message)

    # Add extraction errors to missing info
    for err in extraction_errors:
        missing_info.append(f"Document processing error: {err}")

    # -----------------------------------------------------------------------
    # Rule 1: Check for REJECTION conditions
    # -----------------------------------------------------------------------
    
    # 1a. Blocklisted company
    if is_company_blocked(company_name):
        return WorkflowDecision(
            status="REJECTED",
            explanation=f"The company '{company_name}' appears on the restricted "
                        f"entities list. This application cannot be processed.",
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            missing_info=missing_info,
            next_actions=[
                "This company has been flagged. No further action can be taken.",
                "Contact the compliance team for more information.",
            ],
        )

    # 1b. Tax ID format is completely invalid
    tax_id_check = _find_check(all_checks, "tax_id_format")
    if tax_id_check and not tax_id_check.passed and tax_id_check.severity == "critical":
        # Check if tax ID was provided but is garbage format
        tax_present_check = _find_check(all_checks, "tax_id_present")
        if tax_present_check and tax_present_check.passed:
            # Tax ID was provided but format is wrong → REJECTED
            return WorkflowDecision(
                status="REJECTED",
                explanation=f"The submitted tax identification number does not match "
                            f"the expected format for the selected country. "
                            f"{tax_id_check.message}",
                passed_checks=passed_checks,
                failed_checks=failed_checks,
                missing_info=missing_info,
                next_actions=[
                    "Verify the tax identification number and resubmit.",
                    "Ensure the correct country is selected.",
                    f"Check the expected format: {tax_id_check.message}",
                ],
            )

    # -----------------------------------------------------------------------
    # Rule 2: Check for APPROVAL
    # -----------------------------------------------------------------------
    
    # All critical checks must pass AND no extraction errors
    if len(critical_failures) == 0 and len(extraction_errors) == 0:
        # Build a positive explanation
        explanation = (
            f"All {len(passed_checks)} verification checks passed successfully. "
            f"The vendor submission is complete and consistent."
        )
        if warning_failures:
            explanation += (
                f" Note: {len(warning_failures)} minor warning(s) were flagged "
                f"but do not block approval."
            )

        return WorkflowDecision(
            status="APPROVED",
            explanation=explanation,
            passed_checks=passed_checks,
            failed_checks=failed_checks,
            missing_info=[],
            next_actions=[
                "The vendor has been approved.",
                "Add the vendor to the procurement system.",
                "Send the vendor a confirmation email.",
            ],
        )

    # -----------------------------------------------------------------------
    # Rule 3: Everything else is PENDING
    # -----------------------------------------------------------------------
    
    # Build an explanation listing what's wrong
    issues = []
    for check in critical_failures:
        issues.append(f"• {check.message}")
    for check in warning_failures:
        issues.append(f"• (Warning) {check.message}")
    for err in extraction_errors:
        issues.append(f"• (Error) {err}")

    explanation = (
        f"The submission requires attention. "
        f"{len(critical_failures)} critical issue(s) and "
        f"{len(warning_failures)} warning(s) were found:\n"
        + "\n".join(issues)
    )

    # Build next actions
    next_actions = ["Review the flagged issues below."]
    if missing_info:
        next_actions.append("Request the missing information from the vendor.")
    if any("match" in c.message.lower() for c in critical_failures):
        next_actions.append(
            "Verify name discrepancies with the vendor directly."
        )
    if extraction_errors:
        next_actions.append(
            "Re-upload documents that could not be processed."
        )
    next_actions.append("Once issues are resolved, resubmit for verification.")

    return WorkflowDecision(
        status="PENDING",
        explanation=explanation,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        missing_info=missing_info,
        next_actions=next_actions,
    )


def _find_check(checks: list[CheckResult], check_name: str) -> CheckResult | None:
    """Helper: find a specific check by name in the list."""
    for check in checks:
        if check.check_name == check_name:
            return check
    return None

