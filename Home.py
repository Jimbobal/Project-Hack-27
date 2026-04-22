"""
Forecast Fade Radar — Programme Director Command Deck (landing page).

The first thing a Programme Director sees when they open the app:
    - Portfolio headline numbers (forecast vs actual vs envelope)
    - 2026 forecast band (with M/Q/Y toggle)
    - Top 5 immediate interventions
    - "Ask the Forecast" quick-entry
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.data_loader import (
    load_raw, build_fact, build_latest,
    monthly_portfolio, aggregate_by,
)
from components.forecast_engine import build_forecast, roll_up
from components.prescriptive import build_intervention_queue
from components.llm_narrative import executive_narrative


# ---------------------------------------------------------------------------
# Page config + theme
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Forecast Fade Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Load data (cached)
# ---------------------------------------------------------------------------
raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)
portfolio_m = monthly_portfolio(latest)


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
col_logo, col_title = st.columns([1, 6])
with col_logo:
    st.image("assets/rolls_royce_logo.png", width=100)
with col_title:
    st.markdown("## Forecast Fade Radar")
    st.caption(
        "Predict · Explain · Prescribe — Rolls-Royce Supply-Chain Spend | "
        "Project Hack 27 · Challenge 3"
    )

st.divider()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("Filters")
programmes = sorted(latest["Programme_ID"].dropna().unique().tolist())
programme_filter = st.sidebar.multiselect(
    "Programme", programmes, default=programmes,
    help="Filter all views by programme"
)
horizon = st.sidebar.slider("2026 horizon (months)", 6, 18, 12)
freq_label = st.sidebar.radio("Period granularity", ["Monthly", "Quarterly", "Yearly"],
                              horizontal=True, index=0)
freq_map = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}
freq = freq_map[freq_label]

filtered_latest = latest[latest["Programme_ID"].isin(programme_filter)]

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------
total_forecast = filtered_latest["Forecast_Spend"].sum()
total_actual = filtered_latest["Actual_Spend"].sum()
total_committed = filtered_latest["Committed_Spend"].sum()
abs_error = filtered_latest["Absolute_Error"].sum()
fail_rate = filtered_latest["Forecast_Failed_Flag"].mean() * 100
envelope = portfolio_m["envelope"].sum()

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Forecast Spend (2025)", f"£{total_forecast/1e6:,.1f}M")
k2.metric("Actual Spend (2025)", f"£{total_actual/1e6:,.1f}M",
          delta=f"£{(total_actual-total_forecast)/1e6:+,.1f}M vs forecast",
          delta_color="inverse")
k3.metric("Forecast Fade (|Error|)", f"£{abs_error/1e6:,.1f}M")
k4.metric("Forecast Failure Rate", f"{fail_rate:.1f}%",
          help="Rows where error > CFO confidence tolerance")
k5.metric("Envelope Headroom", f"£{(envelope-total_actual)/1e6:,.1f}M",
          help="Portfolio funding envelope minus actual spend")

st.divider()

# ---------------------------------------------------------------------------
# 2026 Forecast band — the hero chart
# ---------------------------------------------------------------------------
st.markdown("### 2026 Portfolio Forecast · P10–P50–P90 confidence band")

fc = build_forecast(filtered_latest, horizon_months=horizon)
portfolio_fc = roll_up(fc.portfolio, freq=freq)

fig = go.Figure()
# P90 / P10 band
fig.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p90"],
    mode="lines", line=dict(width=0),
    name="P90", showlegend=False, hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p10"],
    mode="lines", line=dict(width=0),
    fill="tonexty", fillcolor="rgba(30, 39, 97, 0.15)",
    name="P10–P90 band",
))
# P50 line
fig.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p50"],
    mode="lines+markers", line=dict(color="#1E2761", width=3),
    name="P50 (central)",
))

# Overlay 2025 actuals for context
actual_rollup = aggregate_by(filtered_latest, by=freq)
fig.add_trace(go.Scatter(
    x=actual_rollup["bucket"], y=actual_rollup["actual"],
    mode="lines+markers", line=dict(color="#FFB800", width=2, dash="dash"),
    name="2025 Actual",
))

fig.update_layout(
    height=430, margin=dict(l=10, r=10, t=20, b=10),
    yaxis_title="£ spend", xaxis_title=None,
    hovermode="x unified", legend=dict(orientation="h", y=-0.2),
    plot_bgcolor="white",
)
fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
fig.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

# Summary stats under the chart
p50_2026 = portfolio_fc["p50"].sum()
p10_2026 = portfolio_fc["p10"].sum()
p90_2026 = portfolio_fc["p90"].sum()
c1, c2, c3 = st.columns(3)
c1.metric("2026 P50", f"£{p50_2026/1e6:,.1f}M")
c2.metric("2026 P10", f"£{p10_2026/1e6:,.1f}M")
c3.metric("2026 P90", f"£{p90_2026/1e6:,.1f}M",
          delta=f"±£{(p90_2026-p10_2026)/2/1e6:,.1f}M uncertainty")

st.divider()

# ---------------------------------------------------------------------------
# Executive narrative + top interventions (two columns)
# ---------------------------------------------------------------------------
left, right = st.columns([1.2, 1])

with left:
    st.markdown("### CFO briefing")
    narrative_context = {
        "portfolio_2025": {
            "forecast_gbp_m": round(total_forecast / 1e6, 1),
            "actual_gbp_m": round(total_actual / 1e6, 1),
            "abs_error_gbp_m": round(abs_error / 1e6, 1),
            "fail_rate_pct": round(fail_rate, 1),
        },
        "portfolio_2026_p50_gbp_m": round(p50_2026 / 1e6, 1),
        "portfolio_2026_p10_gbp_m": round(p10_2026 / 1e6, 1),
        "portfolio_2026_p90_gbp_m": round(p90_2026 / 1e6, 1),
        "top_suppliers_by_error": (
            filtered_latest.groupby(["Supplier_ID", "Supplier_Profile",
                                     "Contract_Type"])["Absolute_Error"]
                .sum().sort_values(ascending=False).head(5)
                .reset_index().to_dict(orient="records")
        ),
    }
    if st.button("Generate briefing", type="primary"):
        with st.spinner("Calling LLM…"):
            st.markdown(executive_narrative(narrative_context))
    else:
        st.info("Click 'Generate briefing' for a live CFO narrative.")

with right:
    st.markdown("### Top 5 interventions this week")
    queue = build_intervention_queue(filtered_latest, top_n=5)
    if queue.empty:
        st.info("No interventions triggered at current filters.")
    else:
        display = queue[["rank", "target", "lever", "action", "recovery_gbp"]].copy()
        display["recovery_gbp"] = display["recovery_gbp"].apply(
            lambda x: f"£{x/1e6:,.2f}M" if x >= 1e6 else f"£{x/1e3:,.0f}k"
        )
        display.columns = ["#", "Target", "Lever", "Action", "Recovery"]
        st.dataframe(display, hide_index=True, use_container_width=True)
        st.caption("Full queue on the Intervention Queue page →")

st.divider()
st.caption(
    "Built for Project Hack 27 · Challenge 3 — Data sources: Forecast_Data, "
    "Supplier_Attributes, Programme_Attributes, Programme_Budget, "
    "Portfolio_Funding_Envelope. Methodology tab documents the modelling stack."
)
