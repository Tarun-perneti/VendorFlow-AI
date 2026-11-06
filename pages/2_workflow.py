"""
Page 2: Live Workflow Execution

Displays real-time progress as each LangGraph node executes.
Shows validation results, the final decision, and an email draft.
"""

import streamlit as st
import time
from core.models import VendorSubmission, WorkflowDecision, CheckResult
from core.database import get_submission, get_checks_for_submission
from workflow.graph import build_workflow
from workflow.state import VendorWorkflowState


def show():
    st.markdown(
        """
        <div class="main-header">
            <h1>⚙️ Workflow Execution</h1>
            <p>Watch the AI-powered verification pipeline process your vendor submission in real time</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Check if there's a pending submission to process
    if "pending_submission" not in st.session_state:
        # No pending — show past results or instructions
        if "workflow_completed_id" in st.session_state:
            _show_results_from_state()
        else:
            st.info(
                "📋 No pending submission. Go to **📝 New Submission** to "
                "submit a vendor application first."
            )

        # Allow viewing a past submission
        st.divider()
        st.markdown("#### 🔍 View Past Submission")
        past_id = st.text_input(
            "Enter a Submission ID:",
            placeholder="e.g., a1b2c3d4-e5f6-...",
        )
        if past_id and st.button("Load Results"):
            _show_past_results(past_id.strip())
        return

    # -----------------------------------------------------------------------
    # There is a pending submission — show it and offer to run
    # -----------------------------------------------------------------------
    submission_dict = st.session_state["pending_submission"]
    submission_id = st.session_state["pending_submission_id"]
    submission = VendorSubmission(**submission_dict)

    # Submission summary card
    st.markdown(f"#### 📋 Submission: {submission.company_name}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"**Country:** {submission.country}")
        st.markdown(f"**Tax ID:** `{submission.tax_id}`")
    with col2:
        st.markdown(f"**Reg #:** {submission.registration_number or 'N/A'}")
        st.markdown(f"**Bank Holder:** {submission.bank_account_holder or 'N/A'}")
    with col3:
        st.markdown(f"**Documents:** {len(submission.uploaded_documents)} file(s)")
        st.markdown(f"**ID:** `{submission_id[:8]}...`")

    st.divider()

    # Already processed?
    if st.session_state.get("workflow_completed_id") == submission_id:
        st.success("✅ This submission has already been processed.")
        _show_results_from_state()
        return

    # Run button
    if st.button(
        "▶️ Run Verification Workflow",
        type="primary",
        use_container_width=True,
    ):
        _execute_workflow(submission_dict, submission_id)


def _execute_workflow(submission_dict: dict, submission_id: str):
    """
    Execute the LangGraph workflow with real-time progress display.
    Uses st.status containers for each stage.
    """
    graph = build_workflow()

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

    stage_names = {
        "extract_documents": ("📄 Document Extraction", "Extracting text from uploaded documents..."),
        "validate_completeness": ("✅ Completeness Validation", "Checking all required fields and documents..."),
        "verify_consistency": ("🔍 Consistency Verification", "Cross-checking submitted information..."),
        "decide": ("⚖️ Decision Engine", "Applying business rules..."),
        "generate_output": ("📧 Output Generation", "Generating report and email draft..."),
    }

    progress_bar = st.progress(0, text="Initializing workflow...")
    all_log_lines = []
    final_decision = None

    try:
        step_count = 0
        for event in graph.stream(initial_state, stream_mode="updates"):
            step_count += 1
            for node_name, node_output in event.items():
                progress_pct = min(step_count * 20, 100)
                stage_info = stage_names.get(node_name, (node_name, "Processing..."))
                progress_bar.progress(progress_pct, text=f"Running: {stage_info[0]}")

                current_log = node_output.get("stage_log", [])
                new_lines = current_log[len(all_log_lines):]
                all_log_lines = current_log

                # Display stage with appropriate state
                with st.status(stage_info[0], expanded=True, state="complete"):
                    for line in new_lines:
                        st.markdown(f"`{line}`")

                    # Highlight the decision
                    if node_name == "decide" and "decision" in node_output:
                        decision_dict = node_output["decision"]
                        final_decision = decision_dict
                        status = decision_dict.get("status", "UNKNOWN")
                        if status == "APPROVED":
                            st.success(f"**✅ Decision: {status}**")
                        elif status == "REJECTED":
                            st.error(f"**❌ Decision: {status}**")
                        else:
                            st.warning(f"**⏳ Decision: {status}**")

                time.sleep(0.3)

        progress_bar.progress(100, text="✅ Workflow complete!")

        # Save results
        final_submission = get_submission(submission_id)
        final_checks = get_checks_for_submission(submission_id)

        st.session_state["workflow_completed_id"] = submission_id
        st.session_state["workflow_result"] = {
            "submission": final_submission,
            "checks": final_checks,
            "log": all_log_lines,
        }

        # Clear pending
        st.session_state.pop("pending_submission", None)
        st.session_state.pop("pending_submission_id", None)

        # Show results
        st.divider()
        _show_results_from_state()

    except Exception as e:
        progress_bar.progress(100, text="❌ Workflow failed!")
        st.error(f"**Workflow error:** {str(e)}")
        import traceback
        with st.expander("Error details"):
            st.code(traceback.format_exc())


def _show_results_from_state():
    """Display workflow results stored in session state."""
    result = st.session_state.get("workflow_result")
    if not result:
        return

    submission = result.get("submission", {})
    checks = result.get("checks", [])
    log_lines = result.get("log", [])

    status = submission.get("status", "UNKNOWN")
    explanation = submission.get("decision_explanation", "")
    email_draft = submission.get("email_draft", "")

    # --- Decision Banner ---
    st.markdown("### 🏁 Final Decision")

    if status == "APPROVED":
        st.markdown(
            '<div class="status-approved" style="font-size:1.5rem;padding:1rem 1.5rem">'
            '✅ APPROVED</div>',
            unsafe_allow_html=True,
        )
    elif status == "REJECTED":
        st.markdown(
            '<div class="status-rejected" style="font-size:1.5rem;padding:1rem 1.5rem">'
            '❌ REJECTED</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="status-pending" style="font-size:1.5rem;padding:1rem 1.5rem">'
            '⏳ PENDING</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    st.markdown(f"**Explanation:** {explanation}")

    # --- Checks Summary ---
    st.markdown("### 📋 Validation Checks")
    passed = [c for c in checks if c.get("passed")]
    failed = [c for c in checks if not c.get("passed")]

    check_col1, check_col2 = st.columns(2)

    with check_col1:
        st.markdown(f"**✅ Passed ({len(passed)})**")
        for c in passed:
            st.markdown(f"- ✅ `{c['check_name']}`")

    with check_col2:
        st.markdown(f"**❌ Failed ({len(failed)})**")
        for c in failed:
            sev = c.get("severity", "")
            icon = "🔴" if sev == "critical" else "🟡"
            st.markdown(
                f"- {icon} `{c['check_name']}` ({sev})  \n"
                f"  {c.get('message', '')}"
            )

    # --- Email Draft ---
    if email_draft:
        st.markdown("### 📧 Email Draft")
        st.caption(
            "⚠️ This is a draft for human review — it will NOT be sent automatically."
        )
        st.text_area("Draft Email", value=email_draft, height=280, disabled=True)

    # --- Full Log ---
    if log_lines:
        with st.expander("📜 Full Workflow Log", expanded=False):
            for line in log_lines:
                st.text(line)


def _show_past_results(submission_id: str):
    """Load and display results for a past submission."""
    submission = get_submission(submission_id)
    if not submission:
        st.error(f"❌ Submission `{submission_id}` not found.")
        return

    checks = get_checks_for_submission(submission_id)
    st.session_state["workflow_completed_id"] = submission_id
    st.session_state["workflow_result"] = {
        "submission": submission,
        "checks": checks,
        "log": [],
    }
    _show_results_from_state()


show()
