"""
Page 1: New Vendor Submission

Professional vendor registration form with:
- Sectioned layout (Company Info, Banking, Documents)
- Input validation with clear error messages
- File upload with PDF support
- Seamless handoff to the Workflow page
"""

import streamlit as st
import os
import shutil
from pathlib import Path
from core.models import VendorSubmission
from core.database import create_submission, init_database
from core.validators import SUPPORTED_COUNTRIES

# Uploads directory
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def show():
    # Page header
    st.markdown(
        """
        <div class="main-header">
            <h1>📝 New Vendor Submission</h1>
            <p>Submit a new vendor application for automated AI-powered verification</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Form
    # -----------------------------------------------------------------------
    with st.form("vendor_form", clear_on_submit=False):

        # --- Company Information ---
        st.markdown("#### 🏢 Company Information")
        col1, col2 = st.columns(2)

        with col1:
            company_name = st.text_input(
                "Company Name *",
                placeholder="e.g., Acme Corp Pvt Ltd",
                help="Legal name as registered with authorities",
            )
            registration_number = st.text_input(
                "Registration Number",
                placeholder="e.g., U12345MH2020PTC123456",
                help="Company registration / incorporation number (CIN, etc.)",
            )

        with col2:
            country = st.selectbox(
                "Country *",
                options=[""] + SUPPORTED_COUNTRIES,
                help="Country where the company is registered. "
                     "Tax ID format is validated based on this selection.",
            )
            tax_id = st.text_input(
                "Tax Identification Number *",
                placeholder="e.g., 29ABCDE1234F1Z5",
                help="GSTIN (India), EIN (US), VAT (UK/DE), UEN (Singapore)",
            )

        st.markdown("")

        # --- Banking Information ---
        st.markdown("#### 🏦 Banking Information")
        col3, col4 = st.columns(2)

        with col3:
            bank_account_holder = st.text_input(
                "Account Holder Name",
                placeholder="e.g., Acme Corp Private Limited",
                help="Name exactly as it appears on the bank account. "
                     "Cross-checked against the company name.",
            )

        with col4:
            bank_account_number = st.text_input(
                "Bank Account Number",
                placeholder="e.g., 1234567890123456",
                help="Stored securely — only last 4 digits are retained.",
                type="password",
            )

        st.markdown("")

        # --- Documents ---
        st.markdown("#### 📎 Supporting Documents")
        st.caption(
            "Upload PDF documents such as **registration certificates**, "
            "**tax certificates (GST/VAT)**, or **bank statements**. "
            "These are processed and cross-checked against the form data."
        )
        uploaded_files = st.file_uploader(
            "Upload PDF Documents",
            type=["pdf"],
            accept_multiple_files=True,
            help="Accepted format: PDF. Maximum 10 MB per file.",
            label_visibility="collapsed",
        )

        if uploaded_files:
            cols = st.columns(min(len(uploaded_files), 4))
            for i, f in enumerate(uploaded_files):
                with cols[i % len(cols)]:
                    size_kb = f.size / 1024
                    st.markdown(
                        f"📄 **{f.name}**  \n"
                        f"<span style='color:#64748B;font-size:0.8rem'>"
                        f"{size_kb:.0f} KB</span>",
                        unsafe_allow_html=True,
                    )

        st.markdown("")
        st.divider()

        # --- Submit ---
        submitted = st.form_submit_button(
            "🚀 Submit for Verification",
            use_container_width=True,
            type="primary",
        )

    # -----------------------------------------------------------------------
    # Handle submission
    # -----------------------------------------------------------------------
    if submitted:
        # Validate
        errors = []
        if not company_name.strip():
            errors.append("Company Name is required.")
        if not country:
            errors.append("Country is required.")
        if not tax_id.strip():
            errors.append("Tax Identification Number is required.")

        if errors:
            for error in errors:
                st.error(f"❌ {error}")
            return

        # Save uploaded files
        saved_paths = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                save_dir = UPLOAD_DIR / "temp"
                save_dir.mkdir(parents=True, exist_ok=True)
                file_path = save_dir / uploaded_file.name
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                saved_paths.append(str(file_path))

        # Create submission
        try:
            submission = VendorSubmission(
                company_name=company_name.strip(),
                registration_number=registration_number.strip(),
                country=country,
                tax_id=tax_id.strip().upper(),
                bank_account_holder=bank_account_holder.strip(),
                bank_account_number=bank_account_number.strip(),
                uploaded_documents=saved_paths,
            )
        except Exception as e:
            st.error(f"❌ Validation error: {e}")
            return

        submission_id = create_submission(submission)

        # Move files to submission directory
        if saved_paths:
            final_dir = UPLOAD_DIR / submission_id
            final_dir.mkdir(parents=True, exist_ok=True)
            new_paths = []
            for old_path in saved_paths:
                filename = Path(old_path).name
                new_path = final_dir / filename
                shutil.move(old_path, new_path)
                new_paths.append(str(new_path))
            submission.uploaded_documents = new_paths

        # Store in session state for workflow page
        st.session_state["pending_submission"] = submission.model_dump()
        st.session_state["pending_submission_id"] = submission_id

        # Success
        st.success(f"✅ **Submission received!** ID: `{submission_id[:8]}...`")
        st.info(
            "👉 Navigate to **⚙️ Workflow** in the sidebar to run the "
            "automated verification pipeline."
        )

    # -----------------------------------------------------------------------
    # How it works section
    # -----------------------------------------------------------------------
    with st.expander("ℹ️ How does the verification work?", expanded=False):
        st.markdown("""
        **VendorFlow AI** processes your submission through 5 automated stages:

        1. **📄 Document Extraction** — Reads uploaded PDFs and extracts text, company names, and tax IDs.
        2. **✅ Completeness Check** — Verifies all required fields and documents are present.
        3. **🔍 Consistency Check** — Cross-checks company name vs. bank holder, tax ID format, and document data.
        4. **⚖️ Decision Engine** — Applies deterministic business rules to produce a verdict.
        5. **📧 Output Generation** — Creates a detailed report and professional email draft.

        **Possible outcomes:**
        - ✅ **APPROVED** — All checks pass. Ready for procurement onboarding.
        - ⏳ **PENDING** — Missing information or discrepancies need human review.
        - ❌ **REJECTED** — Critical validation failure (e.g., invalid tax ID format).
        """)


# Run the page
show()
