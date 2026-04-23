"""
Home — persona switcher dashboard.

Four persona dashboards dispatched from a sidebar selectbox.
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
)

# ---------------------------------------------------------------------------
# Load data (cached)
# ---------------------------------------------------------------------------
raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)
portfolio_m = monthly_portfolio(latest)

# ---------------------------------------------------------------------------
# Sidebar: persona switcher
# ---------------------------------------------------------------------------
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
