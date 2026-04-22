"""
CFO View — portfolio-level financial board view with persona-specific briefings.

Four personas can each generate a tailored LLM briefing:
    1. Programme Director — what number do I commit?
    2. CFO — can I trust the number, how much flex capital?
    3. Commercial Manager — which supplier/contract to intervene on?
    4. Project Controls Lead — which behaviours/data-quality to fix?
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pathlib import Path

from components.data_loader import (
    load_raw, build_fact, build_latest, monthly_portfolio,
    supplier_league, programme_view,
)
from components.forecast_engine import build_forecast, roll_up
from components.prescriptive import build_intervention_queue
from components.llm_narrative import persona_briefing

st.set_page_config(page_title="Portfolio Briefing — Fade Radar",
                   page_icon="\U0001f4bc", layout="wide")

ASSETS = Path(__file__).resolve().parent.parent / "assets"

# ---------------------------------------------------------------------------
# Persona config
# ---------------------------------------------------------------------------
PERSONAS = {
    "Programme Director": {
        "avatar": str(ASSETS / "avatar_programme_director.svg"),
        "question": "What number do I commit to the CFO, and how confident am I?",
        "icon": "\U0001f3af",
    },
    "CFO": {
        "avatar": str(ASSETS / "avatar_cfo.svg"),
        "question": "Can I trust this programme's number, and how much flexible capital can I release?",
        "icon": "\U0001f4bc",
    },
    "Commercial Manager": {
        "avatar": str(ASSETS / "avatar_commercial.svg"),
        "question": "Which supplier or contract do I intervene on this week?",
        "icon": "\U0001f91d",
    },
    "Project Controls Lead": {
        "avatar": str(ASSETS / "avatar_controls.svg"),
        "question": "Which behaviours or data-quality issues do I fix to improve forecasting over time?",
        "icon": "\U0001f4ca",
    },
}

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)
portfolio_m = monthly_portfolio(latest)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("## \U0001f4bc Portfolio Briefing")
st.caption("Board-ready view of portfolio spend, envelope utilisation, and 2026 outlook \u2014 with persona-specific briefings.")

# ---------------------------------------------------------------------------
# Persona selector with avatars
# ---------------------------------------------------------------------------
st.markdown("### Your briefing")
st.markdown("Select your role to receive a tailored briefing from the data.")

persona_names = list(PERSONAS.keys())
cols = st.columns(len(persona_names))

if "cfo_persona" not in st.session_state:
    st.session_state.cfo_persona = None

for i, name in enumerate(persona_names):
    cfg = PERSONAS[name]
    with cols[i]:
        st.image(cfg["avatar"], width=80)
        is_selected = st.session_state.cfo_persona == name
        label = f"{cfg['icon']} {name}" + (" \u2714" if is_selected else "")
        if st.button(label, key=f"persona_btn_{i}", use_container_width=True,
                     type="primary" if is_selected else "secondary"):
            st.session_state.cfo_persona = name
            st.rerun()

# Show briefing if a persona is selected
if st.session_state.cfo_persona:
    persona = st.session_state.cfo_persona
    cfg = PERSONAS[persona]

    st.divider()
    bcol1, bcol2 = st.columns([1, 8])
    with bcol1:
        st.image(cfg["avatar"], width=60)
    with bcol2:
        st.markdown(f"**{cfg['icon']} {persona}**")
        st.caption(f"*{cfg['question']}*")

    # Build context for the LLM
    league = supplier_league(latest).head(10)
    progs = programme_view(latest)
    queue = build_intervention_queue(latest, top_n=10)

    total_forecast = latest["Forecast_Spend"].sum()
    total_actual = latest["Actual_Spend"].sum()
    envelope = portfolio_m["envelope"].sum()

    briefing_context = {
        "portfolio_2025": {
            "forecast_gbp_m": round(total_forecast / 1e6, 1),
            "actual_gbp_m": round(total_actual / 1e6, 1),
            "abs_error_gbp_m": round(latest["Absolute_Error"].sum() / 1e6, 1),
            "fail_rate_pct": round(latest["Forecast_Failed_Flag"].mean() * 100, 1),
            "envelope_gbp_m": round(envelope / 1e6, 1),
            "headroom_gbp_m": round((envelope - total_actual) / 1e6, 1),
            "flexible_gbp_m": round(portfolio_m["flexible"].sum() / 1e6, 1),
        },
        "top_suppliers": league[[
            "Supplier_ID", "Supplier_Profile", "Contract_Type",
            "total_forecast", "total_abs_error", "fail_rate",
        ]].to_dict(orient="records"),
        "programmes": progs.to_dict(orient="records"),
        "top_interventions": (
            queue[["target", "lever", "signal", "action", "recovery_gbp"]]
            .to_dict(orient="records") if not queue.empty else []
        ),
    }

    briefing_key = f"briefing_{persona}"
    if st.button(f"Generate {persona} briefing", type="primary",
                 key=f"gen_btn_{persona}"):
        with st.spinner("Generating briefing\u2026"):
            st.session_state[briefing_key] = persona_briefing(persona, briefing_context)

    if briefing_key in st.session_state:
        st.markdown(st.session_state[briefing_key])

st.divider()

# -----------------------------------------------------------------------
# Granularity toggle
# -----------------------------------------------------------------------
freq_label = st.radio("Period granularity", ["Monthly", "Quarterly", "Yearly"],
                      horizontal=True, index=0)
freq = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}[freq_label]

# -----------------------------------------------------------------------
# Envelope vs Forecast vs Actual
# -----------------------------------------------------------------------
st.markdown("### Envelope utilisation \u00b7 Forecast vs Actual")

pm = portfolio_m.copy()
pm["period_ts"] = pd.to_datetime(pm["period_ts"])
if freq == "M":
    pm["bucket"] = pm["period_ts"].dt.to_period("M").dt.to_timestamp()
elif freq == "Q":
    pm["bucket"] = pm["period_ts"].dt.to_period("Q").dt.to_timestamp()
else:
    pm["bucket"] = pm["period_ts"].dt.to_period("Y").dt.to_timestamp()
roll = pm.groupby("bucket").agg(
    forecast=("forecast", "sum"),
    actual=("actual", "sum"),
    committed=("committed", "sum"),
    envelope=("envelope", "sum"),
    ringfenced=("ringfenced", "sum"),
    flexible=("flexible", "sum"),
).reset_index()

fig = go.Figure()
fig.add_trace(go.Bar(x=roll["bucket"], y=roll["envelope"],
                     name="Envelope", marker_color="#CADCFC"))
fig.add_trace(go.Scatter(x=roll["bucket"], y=roll["forecast"],
                         name="Forecast", mode="lines+markers",
                         line=dict(color="#1E2761", width=3)))
fig.add_trace(go.Scatter(x=roll["bucket"], y=roll["actual"],
                         name="Actual", mode="lines+markers",
                         line=dict(color="#FFB800", width=3, dash="dash")))
fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                  hovermode="x unified", legend=dict(orientation="h", y=-0.15),
                  plot_bgcolor="white", yaxis_title="\u00a3 spend")
fig.update_yaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
fig.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------
# Ringfenced vs flexible utilisation
# -----------------------------------------------------------------------
st.markdown("### Ringfenced vs flexible envelope")

col1, col2 = st.columns(2)
with col1:
    rf_used = min(roll["ringfenced"].sum(), roll["actual"].sum())
    rf_total = roll["ringfenced"].sum()
    fig_rf = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=rf_used / rf_total * 100 if rf_total else 0,
        number={"suffix": "%"},
        title={"text": "Ringfenced utilisation"},
        gauge={"axis": {"range": [0, 110]},
               "bar": {"color": "#1E2761"},
               "steps": [
                   {"range": [0, 80], "color": "#E8F0FE"},
                   {"range": [80, 100], "color": "#CADCFC"},
                   {"range": [100, 110], "color": "#FFCCCC"},
               ]}))
    fig_rf.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_rf, use_container_width=True)

with col2:
    flex_used = max(roll["actual"].sum() - rf_used, 0)
    flex_total = roll["flexible"].sum()
    fig_fx = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=flex_used / flex_total * 100 if flex_total else 0,
        number={"suffix": "%"},
        title={"text": "Flexible utilisation"},
        gauge={"axis": {"range": [0, 110]},
               "bar": {"color": "#FFB800"},
               "steps": [
                   {"range": [0, 60], "color": "#FFF3D6"},
                   {"range": [60, 100], "color": "#FFE099"},
                   {"range": [100, 110], "color": "#FFCCCC"},
               ]}))
    fig_fx.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig_fx, use_container_width=True)

st.caption(
    "Ringfenced: committed, non-reallocatable spend.  "
    "Flexible: headroom available for reallocation across programmes."
)

# -----------------------------------------------------------------------
# Confidence target vs delivered
# -----------------------------------------------------------------------
st.markdown("### CFO confidence target vs delivered")

conf = latest.groupby("Confidence_Band").size().reset_index(name="rows")
conf["pct"] = conf["rows"] / conf["rows"].sum() * 100

fig_c = go.Figure(go.Bar(
    x=conf["Confidence_Band"], y=conf["pct"],
    marker_color=["#1E2761", "#CADCFC", "#FFB800"],
    text=conf["pct"].apply(lambda x: f"{x:.0f}%"),
    textposition="outside",
))
fig_c.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                    yaxis_title="% of forecast rows",
                    plot_bgcolor="white")
fig_c.update_yaxes(ticksuffix="%", gridcolor="#EEE")
st.plotly_chart(fig_c, use_container_width=True)

# Coerce target to float
raw_target = latest["CFO_Confidence_Target"].dropna().iloc[0] if "CFO_Confidence_Target" in latest.columns else 0.8
try:
    target = float(str(raw_target).strip().rstrip("%")) / (100 if "%" in str(raw_target) else 1)
except (ValueError, TypeError):
    target = 0.8
if target > 1:
    target = target / 100
st.info(
    f"**CFO confidence target: {target*100:.0f}%** "
    f"(rows currently meeting tolerance: **{100 - latest['Forecast_Failed_Flag'].mean()*100:.1f}%**). "
    f"Gap-to-target is the single biggest lever to move \u2014 driven primarily by Chronic Fade + T&M suppliers."
)

# -----------------------------------------------------------------------
# 2026 outlook
# -----------------------------------------------------------------------
st.markdown("### 2026 outlook (P10 \u00b7 P50 \u00b7 P90)")

fc = build_forecast(latest, horizon_months=12)
portfolio_fc = roll_up(fc.portfolio, freq=freq)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p90"],
    line=dict(width=0), showlegend=False, hoverinfo="skip",
))
fig2.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p10"],
    line=dict(width=0), fill="tonexty",
    fillcolor="rgba(30,39,97,0.15)", name="P10\u2013P90 band",
))
fig2.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p50"],
    mode="lines+markers", line=dict(color="#1E2761", width=3),
    name="P50 central",
))
fig2.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                   hovermode="x unified",
                   legend=dict(orientation="h", y=-0.15),
                   plot_bgcolor="white", yaxis_title="\u00a3 spend")
fig2.update_yaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
fig2.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig2, use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("2026 P50", f"\u00a3{portfolio_fc['p50'].sum()/1e6:,.1f}M")
c2.metric("2026 P10 (upside)", f"\u00a3{portfolio_fc['p10'].sum()/1e6:,.1f}M")
c3.metric("2026 P90 (downside)", f"\u00a3{portfolio_fc['p90'].sum()/1e6:,.1f}M")
