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
    /* Sidebar background */
    [data-testid="stSidebar"] {{
        background-color: {RR_NAVY};
    }}
    /* Sidebar text white — but NOT dropdown options */
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
    /* Selectbox input box in sidebar — dark bg with gold text */
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
        background-color: #0E1440 !important;
        border: 1px solid #FFB800 !important;
    }}
    [data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div > div {{
        color: #FFB800 !important;
    }}
    [data-testid="stSidebar"] .stSelectbox svg {{
        fill: #FFB800 !important;
        color: #FFB800 !important;
    }}
    /* Dropdown popover — dark text on white */
    div[data-baseweb="popover"] li {{
        color: #0E1440 !important;
    }}
    /* Metric labels */
    [data-testid="stMetricLabel"] {{
        font-weight: 600;
    }}
    /* Red delta for negative metrics */
    [data-testid="stMetricDelta"] svg {{
        display: inline;
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
# Hero header
# ---------------------------------------------------------------------------
hero_left, hero_right = st.columns([5, 1])
with hero_left:
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1E2761 0%, #0E1440 100%);
        padding: 2.5rem 3rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
    ">
        <h1 style="color: white; font-size: 2.8rem; margin: 0 0 0.3rem 0; letter-spacing: -1px;">
            Fade Radar
        </h1>
        <p style="color: #CADCFC; font-size: 1.15rem; margin: 0 0 0.8rem 0;">
            Predict \u00b7 Explain \u00b7 Prescribe &mdash; Rolls-Royce Supply-Chain Spend
        </p>
        <p style="color: rgba(255,255,255,0.6); font-size: 0.85rem; margin: 0;">
            Project Hack 27 \u00b7 Challenge 3
        </p>
    </div>
    """, unsafe_allow_html=True)
with hero_right:
    st.image("assets/rolls_royce_logo.png", width=120)

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
