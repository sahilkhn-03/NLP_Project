"""
app.py
------
Streamlit web application — NL → SQL Query Generator.
Run with:  streamlit run app.py
"""

from __future__ import annotations

import logging
import time
import traceback

import pandas as pd
import streamlit as st

from database import initialize_database, execute_query, get_schema_info
from nlp_processor import parse_question
from sql_generator import generate_sql
from sql_validator import validate_sql, contains_injection_pattern

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config — MUST be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="NL → SQL · Query Generator",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com/streamlit/streamlit",
        "Report a bug": None,
        "About": "Natural Language to SQL Query Generator — College NLP Project",
    },
)

# ---------------------------------------------------------------------------
# CSS (dark glassmorphism design with vibrant cyan input styling)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* ── Fonts ─────────────────────────────────────────────────────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    /* ── Root & background ─────────────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', system-ui, sans-serif;
    }
    .stApp {
        background: #0d0d1a !important;
        background-image:
            radial-gradient(ellipse at 15% 20%, rgba(108,63,255,0.20) 0%, transparent 50%),
            radial-gradient(ellipse at 85% 80%, rgba(56,189,248,0.16) 0%, transparent 50%),
            radial-gradient(ellipse at 50% 50%, rgba(16,185,129,0.08) 0%, transparent 70%) !important;
        background-attachment: fixed !important;
    }

    /* ── Hide default Streamlit chrome ─────────────────────────────────── */
    #MainMenu { visibility: hidden; }
    footer    { visibility: hidden; }
    header    { visibility: hidden; }

    /* ── Sidebar ────────────────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #12103a 0%, #0d0b25 100%) !important;
        border-right: 1px solid rgba(108,99,255,0.25) !important;
    }
    section[data-testid="stSidebar"] * { color: #c8c3f4 !important; }
    section[data-testid="stSidebar"] .stMarkdown h2,
    section[data-testid="stSidebar"] .stMarkdown h3 { color: #a78bfa !important; }

    /* ── Sidebar details/expander ───────────────────────────────────────── */
    section[data-testid="stSidebar"] details {
        background: rgba(108,99,255,0.08) !important;
        border: 1px solid rgba(108,99,255,0.2) !important;
        border-radius: 8px !important;
        margin-bottom: 6px !important;
    }
    section[data-testid="stSidebar"] details summary {
        font-weight: 600 !important; font-size: 0.82rem !important; padding: 6px 10px !important;
    }

    /* ── Buttons ────────────────────────────────────────────────────────── */
    .stButton > button {
        border-radius: 8px !important;
        font-size: 0.82rem !important;
        font-weight: 500 !important;
        transition: all 0.2s cubic-bezier(0.4,0,0.2,1) !important;
        border: 1px solid rgba(108,99,255,0.35) !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(108,99,255,0.4) !important;
        border-color: rgba(108,99,255,0.7) !important;
    }

    /* Sample question buttons in sidebar */
    section[data-testid="stSidebar"] .stButton > button {
        background: rgba(108,99,255,0.12) !important;
        color: #c8c3f4 !important;
        font-size: 0.78rem !important;
        text-align: left !important;
        padding: 7px 12px !important;
        width: 100% !important;
        white-space: normal !important;
        height: auto !important;
        line-height: 1.4 !important;
        margin-bottom: 4px !important;
        border: 1px solid rgba(108,99,255,0.25) !important;
    }
    section[data-testid="stSidebar"] .stButton > button:hover {
        background: rgba(108,99,255,0.3) !important;
        border-color: #a78bfa !important;
        color: #ffffff !important;
    }

    /* Primary buttons (Generate / Submit) */
    .stButton > button[kind="primary"],
    button[data-testid="baseButton-primary"],
    button[kind="primaryFormSubmit"] {
        background: linear-gradient(135deg, #6c3fff, #0284c7) !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        border: none !important;
        font-size: 0.95rem !important;
        box-shadow: 0 4px 15px rgba(108,63,255,0.4) !important;
    }
    .stButton > button[kind="primary"]:hover,
    button[data-testid="baseButton-primary"]:hover,
    button[kind="primaryFormSubmit"]:hover {
        background: linear-gradient(135deg, #7c4dff, #38bdf8) !important;
        box-shadow: 0 6px 24px rgba(56,189,248,0.5) !important;
        transform: translateY(-2px) !important;
    }

    /* ── QUERY BOX INPUT (HIGH-VISIBILITY CYAN TEXT & DARK BACKGROUND) ── */
    div[data-testid="stTextInput"] div[data-baseweb="base-input"],
    div[data-testid="stTextInput"] div[data-baseweb="input"],
    .stTextInput input,
    input[data-testid="stTextInputRootElement"] {
        background-color: #15132f !important;
        background: #15132f !important;
        border: 1.5px solid rgba(139, 92, 246, 0.45) !important;
        border-radius: 12px !important;
        color: #38bdf8 !important;              /* High-tech cyan text when writing */
        caret-color: #38bdf8 !important;        /* Cyan cursor */
        font-size: 1.05rem !important;
        font-weight: 500 !important;
        font-family: 'Inter', system-ui, sans-serif !important;
        padding: 0.7rem 1.1rem !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Focus & Typing state for query box */
    div[data-testid="stTextInput"] div[data-baseweb="base-input"]:focus-within,
    div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
    .stTextInput input:focus {
        background-color: #1a1738 !important;
        background: #1a1738 !important;
        border-color: #38bdf8 !important;
        box-shadow: 0 0 0 3px rgba(56, 189, 248, 0.25), 0 0 20px rgba(139, 92, 246, 0.35) !important;
        color: #38bdf8 !important;              /* Remains vivid cyan while typing */
    }

    /* Query box placeholder */
    .stTextInput input::placeholder {
        color: rgba(167, 139, 250, 0.55) !important;
        font-style: italic;
    }

    /* Selectbox dropdowns */
    div[data-baseweb="select"] > div {
        background-color: #15132f !important;
        border: 1.5px solid rgba(139, 92, 246, 0.4) !important;
        border-radius: 8px !important;
        color: #c8c3f4 !important;
    }

    /* ── Tabs ───────────────────────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: rgba(255,255,255,0.04) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        gap: 6px !important;
        border: 1px solid rgba(108,99,255,0.2) !important;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px !important;
        color: #94a3b8 !important;
        font-weight: 500 !important;
        padding: 8px 22px !important;
        transition: all 0.2s ease !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(108,63,255,0.35), rgba(56,189,248,0.25)) !important;
        color: #38bdf8 !important;
        font-weight: 700 !important;
        border: 1px solid rgba(56,189,248,0.4) !important;
    }

    /* ── Dataframe ──────────────────────────────────────────────────────── */
    .stDataFrame {
        border: 1px solid rgba(108,99,255,0.25) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
        background: #110e26 !important;
    }

    /* ── Expander ───────────────────────────────────────────────────────── */
    details[data-testid="stExpander"] {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(108,99,255,0.2) !important;
        border-radius: 12px !important;
    }

    /* ── Hero & Custom Components ───────────────────────────────────────── */
    .hero-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(108,63,255,0.18);
        border: 1px solid rgba(108,63,255,0.4);
        border-radius: 20px;
        padding: 4px 14px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #a78bfa;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 10px;
    }
    .hero-title {
        font-size: 2.7rem;
        font-weight: 800;
        line-height: 1.15;
        background: linear-gradient(135deg, #a78bfa 0%, #38bdf8 50%, #34d399 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0;
    }
    .hero-sub {
        color: #94a3b8;
        font-size: 1.05rem;
        margin-top: 8px;
        font-weight: 400;
    }
    .metric-card {
        background: rgba(255,255,255,0.04);
        border: 1px solid rgba(108,99,255,0.2);
        border-radius: 12px;
        padding: 16px 20px;
        text-align: center;
        transition: all 0.2s ease;
    }
    .metric-card:hover {
        border-color: rgba(56,189,248,0.5);
        transform: translateY(-2px);
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 800;
        color: #38bdf8;
        line-height: 1;
    }
    .metric-label {
        font-size: 0.75rem;
        color: #94a3b8;
        font-weight: 600;
        margin-top: 5px;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    .result-card-title {
        font-size: 0.75rem;
        font-weight: 700;
        color: #a78bfa;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 12px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: rgba(108,99,255,0.15);
        border: 1px solid rgba(108,99,255,0.3);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.78rem;
        font-weight: 600;
        color: #c4b5fd;
        margin-right: 6px;
    }
    .pill-green {
        background: rgba(16,185,129,0.14);
        border-color: rgba(16,185,129,0.35);
        color: #6ee7b7;
    }
    .pill-blue {
        background: rgba(56,189,248,0.14);
        border-color: rgba(56,189,248,0.35);
        color: #7dd3fc;
    }
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, rgba(108,99,255,0.3), transparent);
        margin: 20px 0;
    }
    .empty-state {
        text-align: center;
        padding: 50px 20px;
        color: #64748b;
    }
    .empty-state-icon { font-size: 3rem; margin-bottom: 12px; }
    .step-badge {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 24px; height: 24px;
        background: linear-gradient(135deg, #6c3fff, #38bdf8);
        border-radius: 50%;
        font-size: 0.7rem;
        font-weight: 700;
        color: white;
        margin-right: 10px;
        flex-shrink: 0;
    }
    .pipeline-step {
        display: flex;
        align-items: flex-start;
        padding: 10px 0;
        border-bottom: 1px solid rgba(108,99,255,0.1);
        color: #94a3b8;
        font-size: 0.88rem;
    }
    .pipeline-step:last-child { border-bottom: none; }
    .pipeline-step-title { font-weight: 600; color: #e2e8f0; }
    .error-card {
        background: rgba(239,68,68,0.1);
        border: 1px solid rgba(239,68,68,0.35);
        border-radius: 12px;
        padding: 16px 20px;
        color: #fca5a5;
        display: flex;
        align-items: flex-start;
        gap: 12px;
    }
    .zero-rows-card {
        background: rgba(16,185,129,0.06);
        border: 1px solid rgba(16,185,129,0.25);
        border-radius: 12px;
        padding: 18px 20px;
        color: #6ee7b7;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_QUESTIONS: list[tuple[str, str]] = [
    ("📋 Basic",     "Show all students"),
    ("📋 Basic",     "List all courses"),
    ("🔍 Filter",    "Find students who scored more than 80 marks"),
    ("🔍 Filter",    "Find students whose attendance is below 75"),
    ("🔍 Filter",    "Show students from the AI department"),
    ("🔍 Filter",    "Show students from the CS department"),
    ("🔍 Filter",    "Show courses with more than 3 credits"),
    ("🔍 Filter",    "Find students with grade A"),
    ("📊 Ranking",   "Show the top 5 students by marks"),
    ("📊 Ranking",   "Show top 3 students by marks"),
    ("📊 Ranking",   "Find students with attendance above 90"),
    ("📈 Aggregate", "Count the number of students in each department"),
    ("📈 Aggregate", "Calculate the average marks of students"),
    ("📈 Aggregate", "Find the highest and lowest marks"),
    ("📈 Aggregate", "Count total number of students"),
    ("📈 Aggregate", "What is the average attendance?"),
    ("🔗 Join",      "List students with their enrolled course names"),
]

CATEGORIES = ["📋 Basic", "🔍 Filter", "📊 Ranking", "📈 Aggregate", "🔗 Join"]

# ---------------------------------------------------------------------------
# Database init (once per session)
# ---------------------------------------------------------------------------
if "db_initialized" not in st.session_state:
    try:
        initialize_database()
        st.session_state["db_initialized"] = True
        st.session_state["db_error"] = None
    except Exception as e:
        st.session_state["db_initialized"] = False
        st.session_state["db_error"] = str(e)
        logger.error("DB init failed: %s", e)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS = {
    "question":      "",
    "q_input":       "",
    "result_df":     None,
    "generated_sql": "",
    "explanation":   "",
    "error_msg":     "",
    "exec_time":     None,
    "row_count":     0,
    "query_history": [],
}
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Core processing function
# ---------------------------------------------------------------------------
def process_question(q: str) -> None:
    """Full pipeline: NLP → SQL generation → validation → execution."""
    st.session_state.update(
        result_df=None,
        generated_sql="",
        explanation="",
        error_msg="",
        exec_time=None,
        row_count=0,
    )

    q = q.strip()
    if not q:
        st.session_state["error_msg"] = "Please type a question first."
        return

    if len(q) > 500:
        st.session_state["error_msg"] = "Question too long (max 500 characters)."
        return

    if contains_injection_pattern(q):
        st.session_state["error_msg"] = (
            "🚫 Your input contains patterns associated with SQL injection. "
            "Please ask a plain English question."
        )
        return

    # 1. NLP parse
    try:
        parsed = parse_question(q)
    except Exception:
        st.session_state["error_msg"] = "NLP parsing failed unexpectedly. Try rephrasing."
        logger.exception("parse_question raised")
        return

    if parsed.error:
        st.session_state["error_msg"] = parsed.error
        return

    # 2. SQL generation
    try:
        gen = generate_sql(parsed)
    except Exception:
        st.session_state["error_msg"] = "SQL generation failed unexpectedly. Try rephrasing."
        logger.exception("generate_sql raised")
        return

    if gen.error:
        st.session_state["error_msg"] = gen.error
        return

    # 3. Security Validation
    try:
        val = validate_sql(gen.sql)
    except Exception:
        st.session_state["error_msg"] = "SQL validation failed unexpectedly."
        logger.exception("validate_sql raised")
        return

    if not val.is_valid:
        st.session_state["error_msg"] = f"Security check failed: {val.error}"
        return

    st.session_state["generated_sql"] = val.clean_sql
    st.session_state["explanation"]   = gen.explanation

    # 4. Safe Execution
    t0 = time.perf_counter()
    try:
        rows = execute_query(val.clean_sql, gen.params)
    except Exception as exc:
        st.session_state["error_msg"] = f"Query execution error: {exc}"
        logger.exception("execute_query raised")
        return

    elapsed = time.perf_counter() - t0
    st.session_state["exec_time"] = elapsed
    st.session_state["row_count"] = len(rows)
    st.session_state["result_df"] = pd.DataFrame(rows) if rows else pd.DataFrame()

    # Query history
    hist = st.session_state["query_history"]
    if q not in hist:
        hist.append(q)
    st.session_state["query_history"] = hist[-20:]

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        """
        <div style="padding:16px 0 8px;">
          <div style="font-size:1.6rem;font-weight:800;color:#a78bfa;">🧠 NL→SQL</div>
          <div style="font-size:0.75rem;color:#94a3b8;margin-top:2px;">
            Natural Language Query Engine
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown(
        "<div style='font-size:0.7rem;font-weight:700;color:#38bdf8;"
        "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>"
        "💡 Sample Questions</div>",
        unsafe_allow_html=True,
    )

    active_cat = st.selectbox(
        "Category",
        CATEGORIES,
        label_visibility="collapsed",
        key="sidebar_cat",
    )

    questions_in_cat = [q for c, q in SAMPLE_QUESTIONS if c == active_cat]
    for q in questions_in_cat:
        if st.button(q, key=f"sq_{abs(hash(q))}", use_container_width=True):
            st.session_state["question"] = q
            st.session_state["q_input"] = q
            process_question(q)
            st.rerun()

    st.divider()

    # Schema viewer
    st.markdown(
        "<div style='font-size:0.7rem;font-weight:700;color:#38bdf8;"
        "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>"
        "🗄️ Database Schema</div>",
        unsafe_allow_html=True,
    )

    try:
        schema_info = get_schema_info()
        TABLE_ICONS = {"students": "👤", "courses": "📚", "enrollments": "📝"}
        for table, cols in schema_info.items():
            icon = TABLE_ICONS.get(table, "📋")
            with st.expander(f"{icon} `{table}`  ({len(cols)} cols)"):
                for c in cols:
                    pk = " 🔑" if c["pk"] else ""
                    st.markdown(
                        f"<div style='font-size:0.8rem;padding:2px 0;"
                        f"color:#94a3b8;'><code style='color:#38bdf8'>{c['name']}</code>"
                        f"<span style='color:#64748b;font-size:0.72rem;'> {c['type']}</span>"
                        f"{pk}</div>",
                        unsafe_allow_html=True,
                    )
    except Exception as e:
        st.warning(f"Schema unavailable: {e}")

    st.divider()

    # History
    if st.session_state["query_history"]:
        st.markdown(
            "<div style='font-size:0.7rem;font-weight:700;color:#38bdf8;"
            "text-transform:uppercase;letter-spacing:0.1em;margin-bottom:8px;'>"
            "🕒 Recent Queries</div>",
            unsafe_allow_html=True,
        )
        for past_q in reversed(st.session_state["query_history"][-5:]):
            if st.button(
                f"↩ {past_q[:38]}{'…' if len(past_q) > 38 else ''}",
                key=f"hist_{abs(hash(past_q))}",
                use_container_width=True,
            ):
                st.session_state["question"] = past_q
                st.session_state["q_input"] = past_q
                process_question(past_q)
                st.rerun()
        st.divider()

    st.markdown(
        "<div style='font-size:0.74rem;color:#64748b;line-height:1.5;'>"
        "⚡ Rule-based NLP engine.<br>"
        "Supports standard queries on college database.<br>"
        "Zero API keys or external models needed."
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# MAIN AREA
# ---------------------------------------------------------------------------
if not st.session_state.get("db_initialized"):
    st.error(
        f"⚠️ Database initialisation failed: {st.session_state.get('db_error')}  \n"
        "Check permissions and restart."
    )
    st.stop()

# ── Hero header ─────────────────────────────────────────────────────────────
st.markdown(
    """
    <div style="padding: 24px 0 10px; text-align:center;">
      <div class="hero-badge">🎓 College NLP Project</div>
      <p class="hero-title">Natural Language → SQL</p>
      <p class="hero-sub">
        Ask questions in plain English · generate verified SQL queries · inspect live results
      </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Stats row ────────────────────────────────────────────────────────────────
try:
    _rows = execute_query("SELECT COUNT(*) AS c FROM students;")
    _students = _rows[0]["c"] if _rows else "—"
    _crows = execute_query("SELECT COUNT(*) AS c FROM courses;")
    _courses = _crows[0]["c"] if _crows else "—"
    _erows = execute_query("SELECT COUNT(*) AS c FROM enrollments;")
    _enrollments = _erows[0]["c"] if _erows else "—"
except Exception:
    _students = _courses = _enrollments = "—"

mc1, mc2, mc3, mc4 = st.columns(4)
for col, val, lbl in [
    (mc1, _students,    "Students"),
    (mc2, _courses,     "Courses"),
    (mc3, _enrollments, "Enrollments"),
    (mc4, len(st.session_state["query_history"]), "Queries Run"),
]:
    with col:
        st.markdown(
            f'<div class="metric-card">'
            f'<div class="metric-value">{val}</div>'
            f'<div class="metric-label">{lbl}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

# ── Query Input Form (supports Enter key natively) ──────────────────────────
with st.form("query_form", clear_on_submit=False, border=False):
    in_col, btn_col, clr_col = st.columns([7, 1.4, 1.1])
    with in_col:
        current_val = st.session_state.get("q_input", "") or st.session_state.get("question", "")
        typed_question = st.text_input(
            label="query_input",
            value=current_val,
            placeholder='e.g. "Show the top 5 students by marks" (press Enter to run)',
            label_visibility="collapsed",
            key="main_query_text",
        )
    with btn_col:
        generate_clicked = st.form_submit_button(
            "⚡ Generate",
            type="primary",
            use_container_width=True,
            help="Generate and execute SQL query (or press Enter in text box)",
        )
    with clr_col:
        clear_clicked = st.form_submit_button(
            "✕ Clear",
            use_container_width=True,
            help="Clear input and results",
        )

if clear_clicked:
    for k, v in _DEFAULTS.items():
        if k != "query_history":
            st.session_state[k] = v
    st.session_state["q_input"] = ""
    st.session_state["question"] = ""
    st.rerun()

if generate_clicked:
    q_to_run = typed_question.strip()
    if q_to_run:
        st.session_state["question"] = q_to_run
        st.session_state["q_input"] = q_to_run
        process_question(q_to_run)
        st.rerun()

st.markdown(
    "<div style='font-size:0.74rem;color:#64748b;margin:-6px 0 6px;'>"
    "⌨️ Tip: Type your query and press <kbd style='background:#1e1b4b;padding:2px 6px;border-radius:4px;border:1px solid #6c3fff;color:#38bdf8'>Enter</kbd> or click ⚡ Generate</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# OUTPUT AREA
# ---------------------------------------------------------------------------
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

error_msg     = st.session_state["error_msg"]
generated_sql = st.session_state["generated_sql"]
explanation   = st.session_state["explanation"]
exec_time     = st.session_state["exec_time"]
row_count     = st.session_state["row_count"]
result_df     = st.session_state["result_df"]

# ── Error display ─────────────────────────────────────────────────────────
if error_msg:
    st.markdown(
        f'<div class="error-card">'
        f'<span style="font-size:1.3rem;">⚠️</span>'
        f'<div><strong style="color:#f87171;">Could not process query</strong><br>'
        f'<span style="font-size:0.9rem;color:#fca5a5;">{error_msg}</span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Results Tabs ──────────────────────────────────────────────────────────
if generated_sql:
    tab_sql, tab_results, tab_explain = st.tabs(
        ["⚙️  Generated SQL", "📊  Results", "💡  Explanation"]
    )

    # ─ Tab 1: SQL ─────────────────────────────────────────────────────────
    with tab_sql:
        lcol, rcol = st.columns([3, 1])
        with lcol:
            st.markdown(
                '<div class="result-card-title">⚙️ Generated SQL Query</div>',
                unsafe_allow_html=True,
            )
            st.code(generated_sql, language="sql")
        with rcol:
            st.markdown("<br>", unsafe_allow_html=True)
            if exec_time is not None:
                st.markdown(
                    f'<div class="pill pill-green">✅ {row_count} row{"s" if row_count != 1 else ""}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="pill pill-blue">⏱ {exec_time * 1000:.1f} ms</div>',
                    unsafe_allow_html=True,
                )
                st.markdown("<br>", unsafe_allow_html=True)
            st.markdown(
                f"<div style='font-size:0.78rem;color:#64748b;'>"
                f"Status: <code style='color:#38bdf8'>Validated & Safe</code>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ─ Tab 2: Results ──────────────────────────────────────────────────────
    with tab_results:
        if result_df is None:
            st.markdown(
                '<div class="empty-state">'
                '<div class="empty-state-icon">🔎</div>'
                '<div class="empty-state-text">No query run yet.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        elif result_df.empty:
            st.markdown(
                '<div class="zero-rows-card">'
                '✅ Query executed successfully but returned <strong>0 rows</strong>.<br>'
                '<span style="font-size:0.85rem;color:#94a3b8;">'
                'Try adjusting the filter criteria or checking sample queries in the sidebar.</span>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            cols_count = len(result_df.columns)
            st.markdown(
                f'<div style="margin-bottom:12px;">'
                f'<span class="pill pill-green">✅ {row_count} rows</span>'
                f'<span class="pill pill-blue">📋 {cols_count} columns</span>'
                f'<span class="pill">⏱ {exec_time * 1000:.1f} ms</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True,
                height=min(420, 40 + 35 * len(result_df)),
            )
            dl_col, _ = st.columns([1.5, 3])
            with dl_col:
                st.download_button(
                    label="⬇️  Download CSV",
                    data=result_df.to_csv(index=False).encode("utf-8"),
                    file_name="query_results.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    # ─ Tab 3: Explanation ──────────────────────────────────────────────────
    with tab_explain:
        st.markdown(
            '<div class="result-card-title">💡 Plain-English Explanation</div>',
            unsafe_allow_html=True,
        )
        st.markdown(explanation if explanation else "_No explanation available._")
        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:0.85rem;color:#64748b;'>"
            "<strong style='color:#a78bfa;'>Input question:</strong>  "
            f"<span style='color:#38bdf8;'>{st.session_state['question']}</span>"
            "</div>",
            unsafe_allow_html=True,
        )

elif not error_msg:
    st.markdown(
        """
        <div class="empty-state">
          <div class="empty-state-icon">🧠</div>
          <div style="font-size:1.15rem;font-weight:700;color:#94a3b8;margin-bottom:8px;">
            Ask a question to get started
          </div>
          <div class="empty-state-text" style="color:#64748b;">
            Type a plain-English question above and press Enter, or click any sample in the sidebar.
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# NLP Pipeline section (collapsible)
# ---------------------------------------------------------------------------
st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

with st.expander("ℹ️  How does the NLP pipeline work?", expanded=False):
    steps = [
        ("Normalisation", "Lower-case, expand contractions (who's → who is), strip punctuation."),
        ("Table Detection", "Keywords like student, course, enrolled are mapped to target tables."),
        ("Intent Detection", "Phrases like count, average, top N determine query category: SELECT / COUNT / AGGREGATE."),
        ("Filter Extraction", "Comparisons (more than 80, below 75) become parameterised WHERE conditions with ? placeholders."),
        ("Sort & Limit", "Top 5, lowest, descending configure ORDER BY and LIMIT."),
        ("Join Detection", "Cross-table queries (with course names) resolve relationships and build 3-table JOINs."),
        ("SQL Assembly", "Query fragments are assembled into safe, syntactically correct SQL."),
        ("Security Validation", "Only SELECT queries pass; DROP, DELETE, INSERT, multi-statements, and injection attacks are rejected."),
        ("Execution", "Clean SQL executes against local SQLite database and results display in real-time."),
    ]
    for i, (title, desc) in enumerate(steps, 1):
        st.markdown(
            f'<div class="pipeline-step">'
            f'<span class="step-badge">{i}</span>'
            f'<div><span class="pipeline-step-title">{title}</span>'
            f'<br><span style="font-size:0.82rem;color:#64748b;">{desc}</span></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:0.8rem;color:#64748b;'>"
        "<strong>Architectural note:</strong> This deterministic rule-based approach guarantees zero hallucinations, "
        "sub-millisecond latency, and full SQL parameterisation."
        "</div>",
        unsafe_allow_html=True,
    )
