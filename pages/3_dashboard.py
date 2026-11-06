"""
Page 3: Dashboard and Run History

Analytics dashboard showing:
- Summary statistics with metric cards
- Status distribution chart
- Recent submissions table
- Detailed view for individual submissions
All data comes from SQLite — no hardcoded values.
"""

import streamlit as st
import pandas as pd
from core.database import (
    get_all_submissions,
    get_submission_stats,
    get_submission,
    get_checks_for_submission,
    get_documents_for_submission,
)


def show():
    st.markdown(
        """
        <div class="main-header">
            <h1>📊 Dashboard</h1>
            <p>Analytics and historical submission data — all from the database</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Summary Statistics
    # -----------------------------------------------------------------------
    stats = get_submission_stats()

    if stats["total"] == 0:
        st.info(
            "📋 No submissions yet. Go to **📝 New Submission** to create "
            "your first vendor application."
        )
        return

    # Metric row
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Total", stats["total"])
    with col2:
        st.metric("✅ Approved", stats["approved"])
    with col3:
        st.metric("⏳ Pending", stats["pending"])
    with col4:
        st.metric("❌ Rejected", stats["rejected"])
    with col5:
        st.metric("Approval Rate", f"{stats['approval_rate']}%")

    if stats.get("processing", 0) > 0:
        st.caption(f"🔄 {stats['processing']} application(s) still processing...")

    st.divider()

    # -----------------------------------------------------------------------
    # Status Distribution
    # -----------------------------------------------------------------------
    col_chart, col_breakdown = st.columns([2, 1])

    with col_chart:
        st.markdown("#### 📉 Status Distribution")
        chart_data = pd.DataFrame({
            "Status": ["Approved", "Pending", "Rejected"],
            "Count": [stats["approved"], stats["pending"], stats["rejected"]],
        })
        if chart_data["Count"].sum() > 0:
            st.bar_chart(chart_data.set_index("Status"))

    with col_breakdown:
        st.markdown("#### 📊 Breakdown")
        total = stats["total"] or 1  # avoid division by zero
        st.markdown(
            f"- ✅ Approved: **{stats['approved']}** "
            f"({stats['approved']/total*100:.0f}%)"
        )
        st.markdown(
            f"- ⏳ Pending: **{stats['pending']}** "
            f"({stats['pending']/total*100:.0f}%)"
        )
        st.markdown(
            f"- ❌ Rejected: **{stats['rejected']}** "
            f"({stats['rejected']/total*100:.0f}%)"
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Submissions Table
    # -----------------------------------------------------------------------
    st.markdown("#### 📋 All Submissions")

    submissions = get_all_submissions()

    if not submissions:
        st.info("No submissions found.")
        return

    # Build display data
    table_data = []
    for sub in submissions:
        status = sub.get("status", "UNKNOWN")
        if status == "APPROVED":
            status_display = "✅ Approved"
        elif status == "REJECTED":
            status_display = "❌ Rejected"
        elif status == "PENDING":
            status_display = "⏳ Pending"
        else:
            status_display = f"🔄 {status}"

        submitted_at = sub.get("submitted_at", "")[:19].replace("T", " ")

        table_data.append({
            "ID": sub["id"][:8] + "...",
            "Company": sub.get("company_name", ""),
            "Country": sub.get("country", ""),
            "Tax ID": sub.get("tax_id", ""),
            "Status": status_display,
            "Submitted": submitted_at,
            "Full ID": sub["id"],
        })

    df = pd.DataFrame(table_data)

    # Display table
    st.dataframe(
        df[["ID", "Company", "Country", "Tax ID", "Status", "Submitted"]],
        use_container_width=True,
        hide_index=True,
    )

    # -----------------------------------------------------------------------
    # Detail View
    # -----------------------------------------------------------------------
    st.divider()
    st.markdown("#### 🔎 Submission Details")

    options = {
        f"{row['Company']}  ({row['ID']}) — {row['Status']}": row["Full ID"]
        for _, row in df.iterrows()
    }

    selected_label = st.selectbox(
        "Select a submission to inspect:",
        options=[""] + list(options.keys()),
    )

    if selected_label and selected_label in options:
        selected_id = options[selected_label]
        _show_detail(selected_id)


def _show_detail(submission_id: str):
    """Show full details for a selected submission."""
    submission = get_submission(submission_id)
    if not submission:
        st.error("Submission not found.")
        return

    status = submission.get("status", "UNKNOWN")

    # Status banner
    if status == "APPROVED":
        st.success("### ✅ APPROVED")
    elif status == "REJECTED":
        st.error("### ❌ REJECTED")
    elif status == "PENDING":
        st.warning("### ⏳ PENDING")
    else:
        st.info(f"### 🔄 {status}")

    # Info columns
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Company Details**")
        st.markdown(f"- **Name:** {submission.get('company_name', 'N/A')}")
        st.markdown(f"- **Registration #:** {submission.get('registration_number') or 'N/A'}")
        st.markdown(f"- **Country:** {submission.get('country', 'N/A')}")
        st.markdown(f"- **Tax ID:** `{submission.get('tax_id', 'N/A')}`")

    with col2:
        st.markdown("**Banking & Timeline**")
        st.markdown(f"- **Account Holder:** {submission.get('bank_account_holder') or 'N/A'}")
        st.markdown(f"- **Account (masked):** `{submission.get('bank_account_masked', 'N/A')}`")
        submitted = submission.get('submitted_at', 'N/A')[:19].replace('T', ' ')
        st.markdown(f"- **Submitted:** {submitted}")
        completed = submission.get('completed_at', '')
        st.markdown(f"- **Completed:** {completed[:19].replace('T', ' ') if completed else 'N/A'}")

    # Explanation
    explanation = submission.get("decision_explanation", "")
    if explanation:
        st.markdown("**Decision Explanation:**")
        st.info(explanation)

    # Validation checks
    checks = get_checks_for_submission(submission_id)
    if checks:
        st.markdown("**Validation Checks:**")
        passed = [c for c in checks if c.get("passed")]
        failed = [c for c in checks if not c.get("passed")]

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"✅ **Passed ({len(passed)})**")
            for c in passed:
                st.markdown(f"- `{c['check_name']}`")
        with c2:
            st.markdown(f"❌ **Failed ({len(failed)})**")
            for c in failed:
                sev = c.get("severity", "")
                icon = "🔴" if sev == "critical" else "🟡"
                st.markdown(f"- {icon} `{c['check_name']}`: {c.get('message', '')}")

    # Email draft
    email_draft = submission.get("email_draft", "")
    if email_draft:
        with st.expander("📧 Email Draft", expanded=False):
            st.text_area("Email", value=email_draft, height=250, disabled=True)

    # Link to workflow
    st.markdown("")
    st.caption(
        f"**Full ID:** `{submission_id}`  \n"
        f"Copy this ID and go to ⚙️ **Workflow** → View Past Submission "
        f"to see the full execution log."
    )


show()
