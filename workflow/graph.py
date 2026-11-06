"""
graph.py — LangGraph workflow assembly

This file wires all the nodes together into an executable graph.
It defines the order of execution and the conditional routing logic.

The graph structure:
    START → extract_documents → validate_completeness → [conditional]
        → verify_consistency → decide → generate_output → END
        → decide → generate_output → END  (if critical fields missing)

Why LangGraph?
- Visual, inspectable pipeline.
- Each node is a separate function (easy to test).
- Conditional routing is explicit (not hidden in if/else chains).
- Built-in support for state management.
"""

from langgraph.graph import StateGraph, START, END
from workflow.state import VendorWorkflowState
from workflow.nodes import (
    extract_documents,
    validate_completeness,
    verify_consistency,
    decide,
    generate_output,
    should_skip_consistency,
)


def build_workflow() -> StateGraph:
    """
    Build and compile the vendor onboarding workflow graph.
    
    Returns a compiled graph that can be invoked with:
        result = graph.invoke(initial_state)
    
    The graph has 5 nodes and 1 conditional edge:
    
    1. extract_documents: Read PDFs and extract text/fields.
    2. validate_completeness: Check all required fields are present.
    3. [CONDITIONAL]: If critical fields missing, skip to decide.
    4. verify_consistency: Cross-check submitted vs. extracted data.
    5. decide: Apply business rules → APPROVED / PENDING / REJECTED.
    6. generate_output: Create email draft, save to database.
    """
    # Create the graph with our state schema
    workflow = StateGraph(VendorWorkflowState)

    # --- Add all nodes ---
    workflow.add_node("extract_documents", extract_documents)
    workflow.add_node("validate_completeness", validate_completeness)
    workflow.add_node("verify_consistency", verify_consistency)
    workflow.add_node("decide", decide)
    workflow.add_node("generate_output", generate_output)

    # --- Define edges (execution order) ---
    
    # Start → extract documents
    workflow.add_edge(START, "extract_documents")

    # Extract → validate completeness
    workflow.add_edge("extract_documents", "validate_completeness")

    # Completeness → CONDITIONAL: either continue or skip
    # This is the key decision point:
    # - If critical fields are missing, there's no point checking consistency.
    # - We skip straight to the decision node (which will produce PENDING/REJECTED).
    workflow.add_conditional_edges(
        "validate_completeness",       # After this node...
        should_skip_consistency,         # ...run this routing function...
        {                               # ...which returns one of these node names:
            "verify_consistency": "verify_consistency",
            "decide": "decide",
        },
    )

    # Consistency → decide
    workflow.add_edge("verify_consistency", "decide")

    # Decide → generate output
    workflow.add_edge("decide", "generate_output")

    # Generate output → END
    workflow.add_edge("generate_output", END)

    # Compile the graph into a runnable application
    compiled = workflow.compile()
    return compiled


def run_workflow(submission_dict: dict, submission_id: str) -> dict:
    """
    Convenience function: build the graph and run it with initial state.
    
    Args:
        submission_dict: Serialized VendorSubmission (from .model_dump()).
        submission_id: The database ID for this submission.
    
    Returns:
        The final state dict after the workflow completes.
    """
    graph = build_workflow()

    # Initial state — all lists start empty
    initial_state: VendorWorkflowState = {
        "submission": submission_dict,
        "submission_id": submission_id,
        "extracted_docs": [],
        "extraction_errors": [],
        "completeness_checks": [],
        "missing_fields": [],
        "consistency_checks": [],
        "decision": {},
        "email_draft": "",
        "current_stage": "starting",
        "stage_log": [],
        "errors": [],
    }

    # Run the workflow — this executes all nodes in order
    final_state = graph.invoke(initial_state)
    return final_state

