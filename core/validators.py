"""
validators.py — Deterministic validation rules for VendorFlow AI

Contains all the business validation logic:
- Completeness checks (are all required fields present?)
- Tax ID format validation (regex by country)
- Name consistency checks (fuzzy string matching)
- Document consistency checks

Why deterministic?
- These rules don't depend on an LLM.
- They produce the same result every time for the same input.
- You can explain exactly what each check does in an interview.
- Critical decisions should NEVER depend on unpredictable LLM output.

Why fuzzy matching for names?
- "Acme Corp Pvt Ltd" and "Acme Corp Private Limited" are the same company.
- Exact string matching would flag this as a mismatch.
- FuzzyWuzzy gives a similarity score (0-100) and we set a threshold.
"""

import re
from core.models import CheckResult, VendorSubmission, ExtractedDocInfo


# ---------------------------------------------------------------------------
# Supported countries and their tax ID patterns
# ---------------------------------------------------------------------------

# Each entry: (country_name, tax_id_type, regex_pattern, description)
# These are used for format validation only — NOT for verifying that the
# ID is genuinely registered with a tax authority.
TAX_ID_PATTERNS = {
    "India": {
        "name": "GSTIN",
        "pattern": r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$",
        "description": "15-character alphanumeric: 2-digit state code + PAN + entity + Z + check digit",
        "example": "29ABCDE1234F1Z5",
    },
    "United States": {
        "name": "EIN",
        "pattern": r"^[0-9]{2}-?[0-9]{7}$",
        "description": "9 digits, optionally formatted as XX-XXXXXXX",
        "example": "12-3456789",
    },
    "United Kingdom": {
        "name": "VAT Number",
        "pattern": r"^(?:GB)?[0-9]{9}(?:[0-9]{3})?$",
        "description": "Optional 'GB' prefix + 9 or 12 digits",
        "example": "GB123456789",
    },
    "Germany": {
        "name": "USt-IdNr",
        "pattern": r"^DE[0-9]{9}$",
        "description": "'DE' prefix + exactly 9 digits",
        "example": "DE123456789",
    },
    "Singapore": {
        "name": "UEN",
        "pattern": r"^(?:[0-9]{8}[A-Z]|[0-9]{9}[A-Z]|[RST][0-9]{2}[A-Z]{2}[0-9]{4}[A-Z])$",
        "description": "9-10 character Unique Entity Number in various formats",
        "example": "201912345K",
    },
}

SUPPORTED_COUNTRIES = list(TAX_ID_PATTERNS.keys())


# ---------------------------------------------------------------------------
# 1. Completeness Checks — Stage 3
# ---------------------------------------------------------------------------

def check_completeness(submission: VendorSubmission) -> list[CheckResult]:
    """
    Verify that all mandatory fields are present and non-empty.
    
    Returns a list of CheckResult objects — one per field checked.
    
    Mandatory fields:
    - company_name (critical)
    - country (critical)
    - tax_id (critical)
    - bank_account_holder (warning)
    - bank_account_number (warning)
    - registration_number (warning)
    - At least one uploaded document (critical)
    """
    checks = []

    # Company name — must have it
    checks.append(CheckResult(
        check_name="company_name_present",
        passed=bool(submission.company_name.strip()),
        severity="critical",
        message="Company name is provided." if submission.company_name.strip()
                else "Company name is missing — this is required.",
    ))

    # Country
    checks.append(CheckResult(
        check_name="country_present",
        passed=bool(submission.country.strip()),
        severity="critical",
        message="Country is provided." if submission.country.strip()
                else "Country is missing — this is required.",
    ))

    # Tax ID
    has_tax_id = bool(submission.tax_id.strip())
    checks.append(CheckResult(
        check_name="tax_id_present",
        passed=has_tax_id,
        severity="critical",
        message="Tax identification number is provided." if has_tax_id
                else "Tax identification number is missing — this is required.",
    ))

    # Bank account holder
    has_holder = bool(submission.bank_account_holder.strip())
    checks.append(CheckResult(
        check_name="bank_holder_present",
        passed=has_holder,
        severity="warning",
        message="Bank account holder name is provided." if has_holder
                else "Bank account holder name is missing.",
    ))

    # Bank account number
    has_account = bool(submission.bank_account_number.strip())
    checks.append(CheckResult(
        check_name="bank_account_present",
        passed=has_account,
        severity="warning",
        message="Bank account number is provided." if has_account
                else "Bank account number is missing.",
    ))

    # Registration number
    has_reg = bool(submission.registration_number.strip())
    checks.append(CheckResult(
        check_name="registration_number_present",
        passed=has_reg,
        severity="warning",
        message="Registration number is provided." if has_reg
                else "Registration number is missing.",
    ))

    # At least one document uploaded
    has_docs = len(submission.uploaded_documents) > 0
    checks.append(CheckResult(
        check_name="documents_uploaded",
        passed=has_docs,
        severity="critical",
        message=f"{len(submission.uploaded_documents)} document(s) uploaded." if has_docs
                else "No supporting documents were uploaded — at least one is required.",
    ))

    return checks


# ---------------------------------------------------------------------------
# 2. Tax ID Format Validation — Stage 4
# ---------------------------------------------------------------------------

def validate_tax_id_format(country: str, tax_id: str) -> CheckResult:
    """
    Validate that the tax ID matches the expected format for the given country.
    
    Important: This ONLY checks the format (regex pattern matching).
    It does NOT verify that the tax ID is actually registered with any authority.
    
    Returns:
    - Passed if the format matches.
    - Failed with severity "critical" if the format is clearly invalid.
    - Failed with severity "warning" if the country is unsupported (can't validate).
    """
    if not tax_id.strip():
        return CheckResult(
            check_name="tax_id_format",
            passed=False,
            severity="critical",
            message="Tax ID is empty — cannot validate format.",
        )

    # Clean the tax ID: remove spaces, convert to uppercase
    cleaned_tax_id = tax_id.strip().upper().replace(" ", "")

    # Check if we support this country
    if country not in TAX_ID_PATTERNS:
        return CheckResult(
            check_name="tax_id_format",
            passed=False,
            severity="warning",
            message=f"Country '{country}' is not in our supported list for tax ID "
                    f"validation. Cannot verify format. "
                    f"Supported countries: {', '.join(SUPPORTED_COUNTRIES)}.",
        )

    pattern_info = TAX_ID_PATTERNS[country]
    pattern = pattern_info["pattern"]

    if re.match(pattern, cleaned_tax_id):
        return CheckResult(
            check_name="tax_id_format",
            passed=True,
            severity="critical",
            message=f"Tax ID '{tax_id}' matches the expected {pattern_info['name']} "
                    f"format for {country}.",
        )
    else:
        return CheckResult(
            check_name="tax_id_format",
            passed=False,
            severity="critical",
            message=f"Tax ID '{tax_id}' does NOT match the expected "
                    f"{pattern_info['name']} format for {country}. "
                    f"Expected format: {pattern_info['description']} "
                    f"(e.g., {pattern_info['example']}).",
        )


# ---------------------------------------------------------------------------
# 3. Country Validation
# ---------------------------------------------------------------------------

def validate_country(country: str) -> CheckResult:
    """Check if the country is in our supported list."""
    if country in SUPPORTED_COUNTRIES:
        return CheckResult(
            check_name="country_supported",
            passed=True,
            severity="info",
            message=f"Country '{country}' is supported for verification.",
        )
    else:
        return CheckResult(
            check_name="country_supported",
            passed=False,
            severity="warning",
            message=f"Country '{country}' is not in our supported list. "
                    f"Some checks may be limited. "
                    f"Supported: {', '.join(SUPPORTED_COUNTRIES)}.",
        )


# ---------------------------------------------------------------------------
# 4. Name Matching — Stage 4
# ---------------------------------------------------------------------------

def _fuzzy_match_score(name1: str, name2: str) -> int:
    """
    Calculate fuzzy similarity between two names (0-100).
    
    Uses thefuzz (formerly fuzzywuzzy) with token_sort_ratio,
    which handles word reordering:
    - "Acme Corp Pvt Ltd" vs "Pvt Ltd Acme Corp" → high score
    
    Falls back to simple containment check if thefuzz is not installed.
    """
    if not name1 or not name2:
        return 0

    try:
        from thefuzz import fuzz
        # token_sort_ratio: splits into words, sorts alphabetically, then compares
        # This handles "Acme Corp Pvt Ltd" vs "Acme Corp Private Limited" well
        return fuzz.token_sort_ratio(name1.lower().strip(), name2.lower().strip())
    except ImportError:
        # Fallback: simple containment check
        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        if n1 == n2:
            return 100
        if n1 in n2 or n2 in n1:
            return 80
        return 0


# Threshold for considering two names as "matching"
# 80 means 80% similar — allows for minor differences like
# "Pvt" vs "Private", "Ltd" vs "Limited"
NAME_MATCH_THRESHOLD = 80


def check_company_name_vs_bank_holder(
    company_name: str, bank_holder: str
) -> CheckResult:
    """
    Cross-check: does the company name match the bank account holder name?
    
    This catches cases where someone submits company "Acme Corp" but the
    bank account is under "John Smith" — a potential red flag.
    
    We use fuzzy matching because legitimate variations exist:
    - "Acme Corp Pvt Ltd" vs "Acme Corp Private Limited" → OK
    - "Acme Corp" vs "Beta Industries" → mismatch
    """
    if not company_name.strip() or not bank_holder.strip():
        return CheckResult(
            check_name="company_vs_bank_holder",
            passed=False,
            severity="warning",
            message="Cannot compare: company name or bank holder is empty.",
        )

    score = _fuzzy_match_score(company_name, bank_holder)

    if score >= NAME_MATCH_THRESHOLD:
        return CheckResult(
            check_name="company_vs_bank_holder",
            passed=True,
            severity="critical",
            message=f"Company name matches bank account holder "
                    f"(similarity: {score}%).",
        )
    else:
        return CheckResult(
            check_name="company_vs_bank_holder",
            passed=False,
            severity="critical",
            message=f"Company name '{company_name}' does NOT closely match "
                    f"bank account holder '{bank_holder}' "
                    f"(similarity: {score}%, threshold: {NAME_MATCH_THRESHOLD}%). "
                    f"This requires human review.",
        )


def check_company_name_vs_document(
    company_name: str, doc_info: ExtractedDocInfo
) -> CheckResult:
    """
    Cross-check: does the company name from the form match what's in the document?
    
    Only runs if the document extraction found a company name.
    """
    doc_name = doc_info.extracted_company_name
    if not doc_name:
        return CheckResult(
            check_name=f"company_vs_doc_{doc_info.source_file}",
            passed=True,  # Can't check, so we don't fail it
            severity="info",
            message=f"No company name was extracted from '{doc_info.source_file}' "
                    f"— skipping name cross-check for this document.",
        )

    score = _fuzzy_match_score(company_name, doc_name)

    if score >= NAME_MATCH_THRESHOLD:
        return CheckResult(
            check_name=f"company_vs_doc_{doc_info.source_file}",
            passed=True,
            severity="warning",
            message=f"Company name matches document '{doc_info.source_file}' "
                    f"(similarity: {score}%).",
        )
    else:
        return CheckResult(
            check_name=f"company_vs_doc_{doc_info.source_file}",
            passed=False,
            severity="warning",
            message=f"Company name '{company_name}' does not match name "
                    f"'{doc_name}' found in '{doc_info.source_file}' "
                    f"(similarity: {score}%). Please verify.",
        )


def check_tax_id_vs_document(
    tax_id: str, doc_info: ExtractedDocInfo
) -> CheckResult:
    """
    Cross-check: does the submitted tax ID match what's in the document?
    
    Only runs if the document extraction found a tax ID.
    """
    doc_tax_id = doc_info.extracted_tax_id
    if not doc_tax_id:
        return CheckResult(
            check_name=f"tax_id_vs_doc_{doc_info.source_file}",
            passed=True,
            severity="info",
            message=f"No tax ID was extracted from '{doc_info.source_file}' "
                    f"— skipping tax ID cross-check for this document.",
        )

    # Clean both for comparison
    clean_submitted = tax_id.strip().upper().replace(" ", "").replace("-", "")
    clean_doc = doc_tax_id.strip().upper().replace(" ", "").replace("-", "")

    if clean_submitted == clean_doc:
        return CheckResult(
            check_name=f"tax_id_vs_doc_{doc_info.source_file}",
            passed=True,
            severity="warning",
            message=f"Tax ID matches the one found in '{doc_info.source_file}'.",
        )
    else:
        return CheckResult(
            check_name=f"tax_id_vs_doc_{doc_info.source_file}",
            passed=False,
            severity="warning",
            message=f"Submitted tax ID '{tax_id}' does not match '{doc_tax_id}' "
                    f"found in '{doc_info.source_file}'. Please verify.",
        )


# ---------------------------------------------------------------------------
# 5. Document Type Checks — Stage 3
# ---------------------------------------------------------------------------

def check_required_document_types(
    extracted_docs: list[ExtractedDocInfo],
) -> list[CheckResult]:
    """
    Check whether the required document types are present.
    
    For a complete submission, we expect at least:
    - One registration certificate OR one tax certificate
    
    This is a soft requirement (warning, not critical) because
    the document might be present but just not classifiable.
    """
    checks = []
    doc_types_found = [d.doc_type for d in extracted_docs if d.doc_type]

    has_registration = "registration_cert" in doc_types_found
    has_tax = "tax_cert" in doc_types_found
    has_bank = "bank_statement" in doc_types_found

    checks.append(CheckResult(
        check_name="has_registration_doc",
        passed=has_registration,
        severity="warning",
        message="Registration certificate document found." if has_registration
                else "No registration certificate document was identified. "
                     "Consider uploading a certificate of incorporation.",
    ))

    checks.append(CheckResult(
        check_name="has_tax_doc",
        passed=has_tax,
        severity="critical",
        message="Tax certificate document found." if has_tax
                else "No tax certificate document was identified. "
                     "Please upload a GST/VAT/EIN certificate.",
    ))

    return checks

