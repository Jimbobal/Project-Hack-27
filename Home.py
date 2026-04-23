"""
Forecast Fade Radar — entry point with grouped sidebar navigation.

Four persona dashboards:
    1. Programme Director — what number do I commit, and how confident am I?
    2. CFO — can I trust the number, and how much flexible capital can I release?
    3. Commercial Manager — which supplier or contract do I intervene on this week?
    4. Project Controls Lead — which behaviours or data-quality issues do I fix?
"""

from __future__ import annotations

import streamlit as st

import base64
from pathlib import Path

from components.persona_views import RR_NAVY

# ---------------------------------------------------------------------------
# Page config (only place this is called — pages must not call it)
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Forecast Fade Radar",
    page_icon="\U0001f4e1",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Navigation with collapsible section groups
# ---------------------------------------------------------------------------
home_page = st.Page("pages/home_content.py", title="Home", icon="\U0001f3e0", default=True)

predict_pages = [
    st.Page("pages/1_📡_Predict_—_Portfolio_Briefing.py",  title="Portfolio Briefing",  icon="\U0001f4bc"),
    st.Page("pages/2_📡_Predict_—_Forecast_Analytics.py",  title="Forecast Fade",       icon="\U0001f4d0"),
    st.Page("pages/3_📡_Predict_—_Forecast_Accuracy.py",   title="Forecast Accuracy",   icon="\U0001f3af"),
    st.Page("pages/4_📡_Predict_—_What_If_Scenarios.py",   title="What-If Scenarios",   icon="\U0001f52e"),
]

explain_pages = [
    st.Page("pages/5_🔍_Explain_—_Supplier_Intelligence.py", title="Supplier Intelligence", icon="\U0001f91d"),
    st.Page("pages/6_🔍_Explain_—_Risk_Heatmap.py",          title="Risk Heatmap",          icon="\U0001f525"),
]

prescribe_pages = [
    st.Page("pages/7_💊_Prescribe_—_Intervention_Queue.py",   title="Intervention Queue",  icon="\U0001f9ed"),
    st.Page("pages/8_💊_Prescribe_—_Ask_the_Forecast.py",     title="Ask the Forecast",    icon="\U0001f4ac"),
]

other_pages = [
    st.Page("pages/10_📊_Methodology.py", title="Methodology", icon="\U0001f4ca"),
]

nav = st.navigation({
    "":            [home_page],
    "Predict":     predict_pages,
    "Explain":     explain_pages,
    "Prescribe":   prescribe_pages,
    "Reference":   other_pages,
})

# ---------------------------------------------------------------------------
# Global Rolls-Royce styling
# ---------------------------------------------------------------------------
st.sidebar.image("assets/fade_radar_logo.png", width=200)
st.sidebar.divider()

st.markdown(f"""
<style>
    /* ---- Modern base ---- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    .main .block-container {{
        padding-top: 3.5rem;
        max-width: 1200px;
    }}

    /* Hide Streamlit's default header bar */
    header[data-testid="stHeader"] {{
        display: none !important;
    }}

    /* ---- Fixed top banner ---- */
    .fade-banner {{
        background: linear-gradient(135deg, #0E1440 0%, #1E2761 60%, #2A3580 100%);
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        z-index: 999999;
        padding: 0.6rem 2rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 2px 8px rgba(14, 20, 64, 0.3);
    }}
    .fade-banner img {{
        height: 40px;
    }}
    .fade-banner .banner-tagline {{
        color: #FFB800;
        font-size: 0.85rem;
        font-weight: 600;
        letter-spacing: 0.08em;
        text-transform: uppercase;
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

st.sidebar.caption(
    "Built for Project Hack 27 \u00b7 Challenge 3\n\n"
    "Predict \u00b7 Explain \u00b7 Prescribe\n\n"
    "Rolls-Royce Supply-Chain Spend"
)

# ---------------------------------------------------------------------------
# Top banner
# ---------------------------------------------------------------------------
_logo_path = Path(__file__).resolve().parent / "assets" / "fade_radar_logo.png"
_logo_b64 = base64.b64encode(_logo_path.read_bytes()).decode()

st.markdown(f"""
<div class="fade-banner">
    <img src="data:image/png;base64,{_logo_b64}" alt="Forecast Fade Radar" />
    <span class="banner-tagline">Predict \u00b7 Explain \u00b7 Prescribe</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Run the selected page
# ---------------------------------------------------------------------------
nav.run()
