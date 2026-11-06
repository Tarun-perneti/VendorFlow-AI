"""
app.py — Main Streamlit entry point for VendorFlow AI

This is the file you run to start the application:
    streamlit run app.py

It sets up:
- Page configuration (title, icon, layout)
- Custom CSS for professional styling
- Multipage navigation (3 pages)
- Database initialization
- Shared sidebar
"""

import streamlit as st
from core.database import init_database

# ---------------------------------------------------------------------------
# Page configuration — must be the first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="VendorFlow AI",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for a clean, professional look
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    /* Main header styling */
    .main-header {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 {
        color: white !important;
        margin: 0;
        font-size: 1.8rem;
    }
    .main-header p {
        color: rgba(255,255,255,0.85);
        margin: 0.3rem 0 0 0;
        font-size: 1rem;
    }

    /* Metric card styling */
    div[data-testid="stMetric"] {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 1rem;
    }
    div[data-testid="stMetric"] label {
        color: #64748B;
        font-size: 0.85rem;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        color: #1E293B;
        font-size: 1.8rem;
    }

    /* Status badges */
    .status-approved {
        background-color: #ECFDF5;
        color: #065F46;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-pending {
        background-color: #FFF7ED;
        color: #9A3412;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }
    .status-rejected {
        background-color: #FEF2F2;
        color: #991B1B;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: 600;
        font-size: 0.85rem;
        display: inline-block;
    }

    /* Button styling */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
    }

    /* Form styling */
    .stTextInput > div > div > input {
        border-radius: 8px;
    }
    .stSelectbox > div > div {
        border-radius: 8px;
    }

    /* Divider */
    hr {
        border-color: #E2E8F0;
    }

    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialize the database (safe to call multiple times)
# ---------------------------------------------------------------------------
init_database()

# ---------------------------------------------------------------------------
# Multipage navigation using st.navigation
# ---------------------------------------------------------------------------
new_submission = st.Page(
    "pages/1_new_submission.py",
    title="New Submission",
    icon="📝",
    default=True,
)
workflow = st.Page(
    "pages/2_workflow.py",
    title="Workflow",
    icon="⚙️",
)
dashboard = st.Page(
    "pages/3_dashboard.py",
    title="Dashboard",
    icon="📊",
)

pg = st.navigation(
    {
        "Vendor Onboarding": [new_submission, workflow],
        "Analytics": [dashboard],
    }
)

# ---------------------------------------------------------------------------
# Shared sidebar content (appears on every page)
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("---")
    st.markdown(
        """
        <div style="text-align: center; padding: 0.5rem;">
            <p style="color: #64748B; font-size: 0.75rem; margin: 0;">
                VendorFlow AI v1.0<br>
                Intelligent Vendor Onboarding
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Run the selected page
# ---------------------------------------------------------------------------
pg.run()
