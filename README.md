# VendorFlow AI — Intelligent Vendor Onboarding Automation

An AI-powered vendor onboarding system that automates the verification of vendor applications using a multi-stage workflow pipeline.

Built as part of the Zamp AI Solutions Analyst case study (PS-2: Operations — Vendor Onboarding).

## What It Does

VendorFlow AI accepts vendor submissions, processes documents, validates information, and makes reasoned approval decisions:

1. **Accepts** vendor details (company info, tax ID, banking info) and PDF documents.
2. **Extracts** text and structured data from uploaded PDFs using pdfplumber + LLM.
3. **Validates** completeness (all required fields present) and consistency (names match, tax ID format correct).
4. **Decides** APPROVED / PENDING / REJECTED using deterministic business rules (not LLM).
5. **Generates** a professional email draft and detailed validation report.
6. **Stores** all submissions, checks, and decisions in SQLite for persistent history.

## Architecture

```
vendorflow/
├── app.py                    # Streamlit entry point
├── pages/
│   ├── 1_new_submission.py   # Vendor registration form
│   ├── 2_workflow.py         # Live workflow execution view
│   └── 3_dashboard.py        # History & analytics dashboard
├── core/
│   ├── models.py             # Pydantic data models
│   ├── database.py           # SQLite operations
│   ├── document.py           # PDF text extraction + classification
│   ├── llm.py                # Gemini LLM client with fallback
│   ├── validators.py         # Deterministic validation rules
│   ├── decision.py           # Rule-based decision engine
│   └── email_draft.py        # Email generation
├── workflow/
│   ├── state.py              # LangGraph shared state
│   ├── nodes.py              # Workflow node functions
│   └── graph.py              # LangGraph graph assembly
└── tests/
    ├── test_backend.py       # Unit tests for all core modules
    ├── test_workflow.py      # LangGraph integration tests
    ├── test_e2e.py           # End-to-end scenario tests
    └── sample_docs/          # Generated sample PDFs
```

## Technology Stack

| Technology | Purpose |
|---|---|
| Python 3.12 | Backend and processing |
| Streamlit | Frontend dashboard |
| LangGraph | Workflow orchestration |
| Pydantic | Input validation |
| SQLite | Persistent storage |
| Google Gemini | Document understanding & email drafting |
| pdfplumber | PDF text extraction |
| thefuzz | Fuzzy string matching |

## Quick Start

### 1. Clone and Setup

```bash
cd vendorflow
python -m venv venv

# Windows
.\venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure API Key (Optional)

```bash
# Copy the example env file
cp .env.example .env

# Edit .env and add your Gemini API key
# Get one free at: https://aistudio.google.com/apikey
```

> **Note:** The app works without an API key — it uses keyword-based document classification and template-based emails as fallback. The LLM enhances document understanding and email quality.

### 3. Generate Sample Test Documents

```bash
python -m tests.generate_sample_docs
```

### 4. Run Tests

```bash
# Unit tests (33 checks)
python -m tests.test_backend

# Workflow integration tests (4 scenarios)
python -m tests.test_workflow

# End-to-end tests with real PDFs (4 scenarios)
python -m tests.test_e2e
```

### 5. Launch the Application

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`.

## Test Scenarios

| # | Scenario | Expected | Validates |
|---|---|---|---|
| 1 | Complete submission with matching docs | **APPROVED** | Happy path — all checks pass |
| 2 | Missing tax certificate document | **PENDING** | Missing required document detection |
| 3 | Company name ≠ bank holder name | **PENDING** | Fuzzy name mismatch flagging |
| 4 | Invalid GSTIN format | **REJECTED** | Tax ID regex validation |

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **Deterministic decisions** | Approval/rejection uses Python rules, not LLM — predictable and explainable |
| **LLM for extraction only** | LLMs are good at understanding messy documents, not at making yes/no decisions |
| **Fuzzy name matching** | "Acme Corp Pvt Ltd" vs "Acme Corp Private Limited" should match (80% threshold) |
| **Conditional routing** | If critical data is missing, skip consistency checks — they'd be meaningless |
| **Masked bank numbers** | Only last 4 digits stored — never expose full account numbers |
| **Graceful LLM fallback** | App works without API key using keyword classification + template emails |

## LangGraph Workflow

```
START → extract_documents → validate_completeness → [conditional]
    → verify_consistency → decide → generate_output → END
    → decide → generate_output → END  (if critical fields missing)
```

Each node is a Python function that reads the shared state, does its work, and writes results back.

## Deployment on Streamlit Community Cloud (Free)

### Step 1: Push to GitHub

```bash
cd vendorflow
git init
git add .
git commit -m "Initial commit: VendorFlow AI v1.0"
```

Create a new repository on [github.com](https://github.com/new) (name it `vendorflow-ai`), then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/vendorflow-ai.git
git branch -M main
git push -u origin main
```

### Step 2: Deploy on Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
2. Click **"New app"**.
3. Select your `vendorflow-ai` repository.
4. Set **Main file path** to: `app.py`
5. Under **Advanced settings > Secrets**, paste:
   ```toml
   GEMINI_API_KEY = "your_actual_api_key_here"
   ```
   *(Get a free key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey))*
6. Click **Deploy**.

Your app will be live at: `https://your-app-name.streamlit.app`

### Other Platforms

Works on any platform that supports Python: Railway, Render, Heroku, Google Cloud Run, etc.

## Project Structure Explained

| File | What It Does | Key Concepts |
|---|---|---|
| `app.py` | Entry point — sets up pages, CSS, sidebar | `st.navigation`, `st.Page` |
| `core/models.py` | Pydantic data models for type safety | `BaseModel`, field validation |
| `core/database.py` | SQLite CRUD operations | SQL, connection management |
| `core/document.py` | PDF text extraction + classification | pdfplumber, keyword matching |
| `core/validators.py` | Deterministic validation rules | regex, fuzzy matching |
| `core/decision.py` | Rule-based decision engine | if/elif logic, severity levels |
| `core/llm.py` | Gemini API client with fallback | API calls, error handling |
| `core/email_draft.py` | Email generation (LLM + templates) | f-strings, template fallback |
| `workflow/state.py` | LangGraph shared state definition | TypedDict |
| `workflow/nodes.py` | 5 workflow node functions | State → partial dict pattern |
| `workflow/graph.py` | Graph assembly + execution | StateGraph, conditional edges |

## License

Built for educational/demonstration purposes as part of the Zamp AI Solutions Analyst case study.

