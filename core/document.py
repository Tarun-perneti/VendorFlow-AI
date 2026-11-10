"""
document.py — PDF text extraction and document understanding

Handles two main tasks:
1. Extract raw text from PDF files using pdfplumber.
2. Use the LLM to classify the document type and extract structured fields.

Why pdfplumber?
- Works well for text-based PDFs (most business documents).
- Pure Python, no external system dependencies.
- Returns text with layout preserved.

Why LLM for classification?
- Business documents come in many formats (invoices, certificates, statements).
- An LLM can understand the MEANING of text, not just pattern-match keywords.
- We use it only when needed and always have a fallback.
"""

import os
from pathlib import Path

from core.models import ExtractedDocInfo
from core.llm import extract_json_from_llm


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract all text from a PDF file using pdfplumber.
    
    Returns the concatenated text from all pages.
    Returns an empty string if extraction fails.
    
    Why try/except? PDFs can be corrupted, password-protected,
    or contain only images (no extractable text).
    """
    try:
        import pdfplumber

        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return "\n".join(text_parts)

    except Exception as e:
        print(f"[Document] Failed to extract text from {file_path}: {e}")
        return ""


def classify_and_extract(filename: str, raw_text: str) -> ExtractedDocInfo:
    """
    Given the raw text from a PDF, use the LLM to:
    1. Classify the document type (registration cert, tax cert, bank statement, etc.)
    2. Extract relevant fields (company name, registration number, tax ID, etc.)
    
    Falls back to keyword-based classification if the LLM is unavailable.
    
    Args:
        filename: Name of the PDF file (helps with classification hints).
        raw_text: The extracted text content of the PDF.
    
    Returns:
        ExtractedDocInfo with all available fields populated.
    """
    # If there's no text to analyze, return a minimal result
    if not raw_text or len(raw_text.strip()) < 10:
        return ExtractedDocInfo(
            source_file=filename,
            doc_type="unknown",
            raw_text=raw_text,
            extraction_method="pdfplumber",
            confidence_notes="Document appears empty or unreadable. "
                             "It may be a scanned image without OCR text.",
        )

    # Try LLM-based extraction first
    llm_result = _llm_classify_and_extract(filename, raw_text)
    if llm_result is not None:
        return llm_result

    # Fallback: keyword-based classification (no LLM needed)
    return _keyword_classify_and_extract(filename, raw_text)


def _llm_classify_and_extract(filename: str, raw_text: str) -> ExtractedDocInfo | None:
    """
    Use the LLM to classify a document and extract structured fields.
    
    The prompt asks the LLM to return JSON matching our ExtractedDocInfo schema.
    We explicitly tell it NOT to invent information — only extract what's there.
    
    Returns None if the LLM is unavailable or fails.
    """
    # Truncate very long documents to avoid token limits
    truncated_text = raw_text[:4000] if len(raw_text) > 4000 else raw_text

    prompt = f"""You are analyzing a business document for vendor onboarding verification.

Document filename: {filename}

Document text:
---
{truncated_text}
---

Analyze this document and return a JSON object with these fields:
- "doc_type": one of "registration_cert", "tax_cert", "bank_statement", or "unknown"
- "extracted_company_name": the company name found in the document, or null if not found
- "extracted_registration_number": any registration/incorporation number, or null
- "extracted_tax_id": any tax identification number (GSTIN, EIN, VAT, etc.), or null
- "extracted_account_holder": bank account holder name, or null
- "confidence_notes": brief note about extraction confidence

IMPORTANT RULES:
- Only extract information that is actually present in the text.
- Do NOT invent or guess any values.
- If a field is not found, set it to null.
- Return ONLY valid JSON, no other text.
"""

    system_instruction = (
        "You are a document analysis assistant. Extract information accurately. "
        "Never fabricate data. Return only valid JSON."
    )

   result = extract_json_from_llm(prompt, system_instruction)

if result is None:
    print(f"[Document] Gemini extraction failed for {filename}. Using fallback.")
    return None

print(f"[Document] Gemini extraction successful for {filename}")

    return ExtractedDocInfo(
        source_file=filename,
        doc_type=result.get("doc_type", "unknown"),
        extracted_company_name=result.get("extracted_company_name"),
        extracted_registration_number=result.get("extracted_registration_number"),
        extracted_tax_id=result.get("extracted_tax_id"),
        extracted_account_holder=result.get("extracted_account_holder"),
        raw_text=raw_text,
        extraction_method="llm",
        confidence_notes=result.get("confidence_notes", "Extracted via LLM"),
    )


def _keyword_classify_and_extract(filename: str, raw_text: str) -> ExtractedDocInfo:
    """
    Fallback classification using simple keyword matching.
    
    This runs when the LLM is unavailable. It's less accurate but
    ensures the workflow can still proceed.
    
    Why keywords? Common business documents contain predictable terms:
    - Registration certificates mention "certificate", "incorporation", "registered"
    - Tax documents mention "tax", "GST", "VAT", "EIN"
    - Bank statements mention "bank", "account", "statement", "balance"
    """
    text_lower = raw_text.lower()
    fname_lower = filename.lower()

    # Classify based on keywords in the text and filename
    # Order matters: check more specific types first
    doc_type = "unknown"

    # Check for bank documents first (most specific keywords)
    bank_keywords = ["bank statement", "account statement", "bank account",
                      "account number", "ifsc", "swift", "account holder"]
    if any(kw in text_lower or kw in fname_lower for kw in bank_keywords):
        doc_type = "bank_statement"

    # Check for tax-related documents (check before registration because
    # a "GST Registration Certificate" is a tax document, not a registration cert)
    tax_keywords = ["tax", "gst", "gstin", "vat", "ein", "tax identification",
                     "tax registration", "tax certificate", "goods and services tax"]
    if any(kw in text_lower or kw in fname_lower for kw in tax_keywords):
        doc_type = "tax_cert"

    # Check for registration documents (only if not already classified)
    if doc_type == "unknown":
        reg_keywords = ["certificate of incorporation", "registration certificate",
                         "registered office", "company registration", "cin",
                         "certificate of registration", "incorporation",
                         "ministry of corporate affairs"]
        if any(kw in text_lower or kw in fname_lower for kw in reg_keywords):
            doc_type = "registration_cert"

    return ExtractedDocInfo(
        source_file=filename,
        doc_type=doc_type,
        raw_text=raw_text,
        extraction_method="pdfplumber",
        confidence_notes="Classified using keyword matching (LLM unavailable). "
                         "Structured field extraction was not performed.",
    )


def process_uploaded_document(file_path: str) -> ExtractedDocInfo:
    """
    Main entry point: process a single uploaded document.
    
    1. Extract text with pdfplumber
    2. Classify and extract fields (LLM or keyword fallback)
    3. Return structured ExtractedDocInfo
    
    This is the function that workflow nodes call.
    """
    filename = Path(file_path).name

    # Step 1: Extract raw text
    raw_text = extract_text_from_pdf(file_path)

    # Step 2: Classify and extract structured fields
    doc_info = classify_and_extract(filename, raw_text)

    return doc_info

