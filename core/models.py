"""
models.py — Pydantic data models for VendorFlow AI

These models define the shape of data flowing through the system.
Pydantic automatically validates that data matches these schemas,
catching errors early (e.g., missing fields, wrong types).

Why Pydantic?
- Automatic validation: if someone passes an int where we expect str, it errors immediately.
- Serialization: easy .model_dump() to convert to dict for database storage.
- Documentation: the model IS the documentation of what data looks like.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. Vendor Submission — what the user fills in the form
# ---------------------------------------------------------------------------
class VendorSubmission(BaseModel):
    """
    Represents the vendor's application form data.
    This is the raw input before any processing or validation.
    """
    company_name: str = Field(
        default="",
        description="Legal name of the vendor company"
    )
    registration_number: str = Field(
        default="",
        description="Company registration number (e.g., CIN for India)"
    )
    country: str = Field(
        default="",
        description="Country where the company is registered"
    )
    tax_id: str = Field(
        default="",
        description="Tax identification number (GSTIN, EIN, VAT, etc.)"
    )
    bank_account_holder: str = Field(
        default="",
        description="Name on the bank account"
    )
    bank_account_number: str = Field(
        default="",
        description="Bank account number (will be masked before storage)"
    )
    uploaded_documents: list[str] = Field(
        default_factory=list,
        description="List of file paths to uploaded PDF documents"
    )


# ---------------------------------------------------------------------------
# 2. Extracted Document Info — what we pull out of each PDF
# ---------------------------------------------------------------------------
class ExtractedDocInfo(BaseModel):
    """
    Structured information extracted from a single uploaded document.
    The LLM or pdfplumber fills this in during the extraction stage.
    """
    source_file: str = Field(
        description="Filename of the PDF this was extracted from"
    )
    doc_type: Optional[str] = Field(
        default=None,
        description="Classified type: 'registration_cert', 'tax_cert', 'bank_statement', or 'unknown'"
    )
    extracted_company_name: Optional[str] = Field(
        default=None,
        description="Company name found in the document"
    )
    extracted_registration_number: Optional[str] = Field(
        default=None,
        description="Registration number found in the document"
    )
    extracted_tax_id: Optional[str] = Field(
        default=None,
        description="Tax ID found in the document"
    )
    extracted_account_holder: Optional[str] = Field(
        default=None,
        description="Account holder name found in the document"
    )
    raw_text: str = Field(
        default="",
        description="Full text extracted from the document"
    )
    extraction_method: str = Field(
        default="pdfplumber",
        description="How the text was extracted: 'pdfplumber' or 'llm'"
    )
    confidence_notes: str = Field(
        default="",
        description="Any caveats about extraction quality"
    )


# ---------------------------------------------------------------------------
# 3. Check Result — outcome of a single validation check
# ---------------------------------------------------------------------------
class CheckResult(BaseModel):
    """
    Result of one validation check (e.g., "is the tax ID format valid?").
    Multiple CheckResults form the evidence for the final decision.
    
    Severity levels:
    - "critical": Must pass for approval. Failure = PENDING or REJECTED.
    - "warning": Should be reviewed but doesn't block approval.
    - "info": Informational note, no impact on decision.
    """
    check_name: str = Field(description="Identifier like 'tax_id_format' or 'company_name_match'")
    passed: bool = Field(description="Whether this check passed")
    severity: str = Field(description="'critical', 'warning', or 'info'")
    message: str = Field(description="Human-readable explanation of the result")


# ---------------------------------------------------------------------------
# 4. Workflow Decision — the final output
# ---------------------------------------------------------------------------
class WorkflowDecision(BaseModel):
    """
    The final decision produced by the decision engine.
    Contains everything needed to explain the outcome to a human reviewer.
    """
    status: str = Field(
        description="'APPROVED', 'PENDING', or 'REJECTED'"
    )
    explanation: str = Field(
        description="Human-readable summary of why this decision was made"
    )
    passed_checks: list[CheckResult] = Field(
        default_factory=list,
        description="All checks that passed"
    )
    failed_checks: list[CheckResult] = Field(
        default_factory=list,
        description="All checks that failed"
    )
    missing_info: list[str] = Field(
        default_factory=list,
        description="List of missing information the vendor should provide"
    )
    next_actions: list[str] = Field(
        default_factory=list,
        description="Suggested next steps for the vendor or reviewer"
    )
    email_draft: Optional[str] = Field(
        default=None,
        description="Draft email to send to the vendor"
    )


# ---------------------------------------------------------------------------
# 5. Submission Record — what we store in the database
# ---------------------------------------------------------------------------
class SubmissionRecord(BaseModel):
    """
    Database-facing model. Represents a row in the submissions table.
    Bank account is already masked when this object is created.
    """
    id: str = Field(description="UUID for this submission")
    company_name: str
    registration_number: str = ""
    country: str = ""
    tax_id: str = ""
    bank_account_holder: str = ""
    bank_account_masked: str = Field(
        default="",
        description="Masked bank account showing only last 4 digits"
    )
    status: str = Field(default="PROCESSING")
    decision_explanation: Optional[str] = None
    email_draft: Optional[str] = None
    submitted_at: str = Field(
        default_factory=lambda: datetime.now().isoformat()
    )
    completed_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper function
# ---------------------------------------------------------------------------
def mask_account_number(account_number: str) -> str:
    """
    Mask a bank account number, showing only the last 4 digits.
    Example: "1234567890123456" -> "************3456"
    
    Why? Security requirement — we never store or display full account numbers.
    """
    if not account_number or len(account_number) < 4:
        return "****"
    return "*" * (len(account_number) - 4) + account_number[-4:]

