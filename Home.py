"""
Forecast Fade Radar — Home page with persona switcher.

Four persona dashboards:
    1. Programme Director — what number do I commit, and how confident am I?
    2. CFO — can I trust the number, and how much flexible capital can I release?
    3. Commercial Manager — which supplier or contract do I intervene on this week?
    4. Project Controls Lead — which behaviours or data-quality issues do I fix?
"""

from __future__ import annotations

import streamlit as st

from components.data_loader import (
    load_raw, build_fact, build_latest, monthly_portfolio,
)
from components.persona_views import (
    render_programme_director,
    render_cfo,
    render_commercial_manager,
    render_project_controls,
    RR_NAVY,
)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Forecast Fade Radar",
    page_icon="\U0001f4e1",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Global Rolls-Royce styling
# ---------------------------------------------------------------------------
st.markdown(f"""
<style>
    /* ---- Modern base ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    .main .block-container {{
        padding-top: 2rem;
        max-width: 1200px;
    }}

    /* ---- Sidebar ---- */
    [data-testid="stSidebar"] {{
        background-color: {RR_NAVY};
    }}
    [data-testid="stSidebar"] > div {{
        color: white;
    }}
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] .stMarkdown *,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] .stDivider {{
        color: white !important;
    }}
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
        background-color: #0E1440 !important;
        border: 1px solid #FFB800 !important;
        border-radius: 8px;
    }}
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div > div {{
        color: #FFB800 !important;
    }}
    [data-testid="stSidebar"] .stSelectbox svg {{
        fill: #FFB800 !important;
        color: #FFB800 !important;
    }}
    div[data-baseweb="popover"] li {{
        color: #0E1440 !important;
    }}

    /* ---- Metric cards ---- */
    [data-testid="stMetric"] {{
        background: white;
        border: 1px solid #E8ECF4;
        border-radius: 12px;
        padding: 1rem 1.25rem;
        box-shadow: 0 1px 3px rgba(14, 20, 64, 0.06);
    }}
    [data-testid="stMetricLabel"] {{
        font-weight: 600;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        color: #6B7280 !important;
    }}
    [data-testid="stMetricValue"] {{
        font-weight: 700;
        color: #0E1440 !important;
    }}

    /* ---- Section headers ---- */
    .main h3 {{
        color: #1E2761;
        font-weight: 700;
        font-size: 1.25rem;
        border-bottom: 2px solid #E8ECF4;
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
    }}

    /* ---- Dataframes ---- */
    [data-testid="stDataFrame"] {{
        border: 1px solid #E8ECF4;
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 1px 3px rgba(14, 20, 64, 0.06);
    }}

    /* ---- Buttons ---- */
    .stButton > button {{
        border-radius: 8px;
        font-weight: 600;
        transition: all 0.2s ease;
    }}
    .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(30, 39, 97, 0.2);
    }}

    /* ---- Plotly charts ---- */
    [data-testid="stPlotlyChart"] {{
        background: white;
        border: 1px solid #E8ECF4;
        border-radius: 12px;
        padding: 0.5rem;
        box-shadow: 0 1px 3px rgba(14, 20, 64, 0.06);
    }}

    /* ---- Dividers ---- */
    hr {{
        border-color: #E8ECF4 !important;
        margin: 1.5rem 0 !important;
    }}

    /* ---- Info boxes ---- */
    .stAlert {{
        border-radius: 10px;
    }}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load data (cached)
# ---------------------------------------------------------------------------
raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)
portfolio_m = monthly_portfolio(latest)

# ---------------------------------------------------------------------------
# Sidebar: logo + persona switcher
# ---------------------------------------------------------------------------
st.sidebar.image("assets/rolls_royce_logo.png", width=120)
st.sidebar.markdown("# Forecast Fade Radar")
st.sidebar.divider()

PERSONAS = [
    "Programme Director",
    "CFO",
    "Commercial Manager",
    "Project Controls Lead",
]

if "persona" not in st.session_state:
    st.session_state.persona = PERSONAS[0]

selected = st.sidebar.selectbox(
    "Select persona",
    PERSONAS,
    index=PERSONAS.index(st.session_state.persona),
    key="persona_selector",
)
st.session_state.persona = selected

st.sidebar.divider()
st.sidebar.caption(
    "Built for Project Hack 27 \u00b7 Challenge 3\n\n"
    "Predict \u00b7 Explain \u00b7 Prescribe\n\n"
    "Rolls-Royce Supply-Chain Spend"
)

# ---------------------------------------------------------------------------
# Hero header — official Fade Radar branding
# ---------------------------------------------------------------------------
_, logo_col, _ = st.columns([1, 2, 1])
with logo_col:
    st.image("assets/fade_radar_logo.png", use_container_width=True)

# ---------------------------------------------------------------------------
# Dispatch to persona view
# ---------------------------------------------------------------------------
if selected == "Programme Director":
    render_programme_director(latest, fact, portfolio_m)
elif selected == "CFO":
    render_cfo(latest, fact, portfolio_m)
elif selected == "Commercial Manager":
    render_commercial_manager(latest, fact, portfolio_m)
elif selected == "Project Controls Lead":
    render_project_controls(latest, fact, portfolio_m)
