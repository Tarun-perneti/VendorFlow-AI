"""
state.py — LangGraph shared state definition

This file defines the TypedDict that flows through every node in the workflow.
Think of it as the "memory" of the pipeline — each node reads from it,
does its work, and writes its results back.

Why TypedDict (not a Pydantic model)?
- LangGraph requires TypedDict for its state schema.
- TypedDict is a plain Python type hint — no validation overhead at each step.
- We use Pydantic models INSIDE the state (serialized as dicts) for the actual data.
"""

from typing import TypedDict


class VendorWorkflowState(TypedDict):
    """
    Shared state for the vendor onboarding workflow.
    
    Every workflow node receives this state and returns a dict
    with only the keys it wants to update. LangGraph merges
    the updates into the shared state automatically.
    """

    # --- Input (set once at the start) ---
    submission: dict          # Serialized VendorSubmission (from form)
    submission_id: str        # Database ID for this submission

    # --- Stage 2: Document Extraction output ---
    extracted_docs: list      # List of ExtractedDocInfo dicts
    extraction_errors: list   # List of error message strings

    # --- Stage 3: Completeness Validation output ---
    completeness_checks: list # List of CheckResult dicts
    missing_fields: list      # List of missing field descriptions

    # --- Stage 4: Consistency Verification output ---
    consistency_checks: list  # List of CheckResult dicts

    # --- Stage 5: Decision Engine output ---
    decision: dict            # Serialized WorkflowDecision

    # --- Stage 6: Output Generation ---
    email_draft: str          # Generated email text

    # --- Tracking (updated by every node) ---
    current_stage: str        # Name of the currently executing stage
    stage_log: list           # List of human-readable log entries
    errors: list              # List of error messages from any stage

