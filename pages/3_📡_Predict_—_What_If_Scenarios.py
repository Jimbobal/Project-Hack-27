"""
What-If Scenarios — simulate interventions and see the forecast impact.

Users select an intervention type, pick a target, and see before/after
comparison of KPIs and the 2026 forecast band.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from components.data_loader import load_raw, build_fact, build_latest
from components.forecast_engine import build_forecast, roll_up

st.set_page_config(page_title="What-If Scenarios — Fade Radar",
                   page_icon="\U0001f52e", layout="wide")

st.sidebar.image("assets/fade_radar_logo.png", width=200)

st.markdown("## \U0001f52e What-If Scenarios")
st.caption("Simulate an intervention and see the impact on the 2026 forecast in real time.")

# Palette
RR_NAVY = "#1E2761"
RR_GOLD = "#FFB800"
RR_RED = "#D72638"
RR_GREEN = "#2E8B57"

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)

# ---------------------------------------------------------------------------
# Intervention selector
# ---------------------------------------------------------------------------
INTERVENTIONS = {
    "Migrate supplier from T&M to Fixed Price": {
        "target_col": "Supplier_ID",
        "filter": lambda df: df[df["Contract_Type"] == "T&M"],
        "reduction": 0.55,
        "description": "Reduces forecast error by 55% for the selected T&M supplier by simulating a Fixed Price migration.",
    },
    "Increase revision cadence": {
        "target_col": "Supplier_ID",
        "filter": lambda df: df,
        "reduction": 0.35,
        "description": "Reduces forecast error by 35% by simulating more frequent forecast revisions.",
    },
    "Dual-source a commodity": {
        "target_col": "Commodity",
        "filter": lambda df: df,
        "reduction": 0.45,
        "description": "Reduces forecast error by 45% for the selected commodity by simulating dual-sourcing.",
    },
    "Scope freeze on programme": {
        "target_col": "Programme_ID",
        "filter": lambda df: df,
        "reduction": 0.30,
        "description": "Reduces forecast error by 30% for the selected programme by simulating a scope freeze.",
    },
}

st.divider()

col1, col2 = st.columns(2)
with col1:
    intervention = st.selectbox("Select intervention", list(INTERVENTIONS.keys()))
with col2:
    cfg = INTERVENTIONS[intervention]
    filtered = cfg["filter"](latest)
    targets = sorted(filtered[cfg["target_col"]].dropna().unique().tolist())
    target = st.selectbox(f"Select {cfg['target_col'].replace('_', ' ').lower()}", targets)

st.info(f"**Simulation:** {cfg['description']}")

if not target:
    st.warning("Please select a target to simulate.")
    st.stop()

# ---------------------------------------------------------------------------
# Simulate: modify latest by reducing error for the target
# ---------------------------------------------------------------------------
modified = latest.copy()
mask = modified[cfg["target_col"]] == target

# Reduce the gap between forecast and actual
original_error = modified.loc[mask, "Absolute_Error"].sum()
reduction_pct = cfg["reduction"]

# Adjust Forecast_Spend toward Actual_Spend by the reduction %
variance = modified.loc[mask, "Forecast_Spend"] - modified.loc[mask, "Actual_Spend"]
modified.loc[mask, "Forecast_Spend"] = (
    modified.loc[mask, "Forecast_Spend"] - variance * reduction_pct
)
modified.loc[mask, "Absolute_Error"] = (
    modified.loc[mask, "Absolute_Error"] * (1 - reduction_pct)
)
# Recalculate failure flag (error > tolerance implies failure)
if "CFO_Confidence_Target" in modified.columns:
    raw_target = modified["CFO_Confidence_Target"].dropna().iloc[0]
    try:
        tol = float(str(raw_target).strip().rstrip("%"))
        if tol > 1:
            tol = tol / 100
    except (ValueError, TypeError):
        tol = 0.1
    modified.loc[mask, "Forecast_Failed_Flag"] = (
        (modified.loc[mask, "Absolute_Error"] /
         modified.loc[mask, "Forecast_Spend"].replace(0, np.nan)) > tol
    ).astype(int)

recovered_error = original_error - modified.loc[mask, "Absolute_Error"].sum()

st.divider()

# ---------------------------------------------------------------------------
# Before vs After KPIs
# ---------------------------------------------------------------------------
st.markdown("### Before vs After")

def _kpis(df, label):
    return {
        "label": label,
        "total_error": df["Absolute_Error"].sum(),
        "fail_rate": df["Forecast_Failed_Flag"].mean() * 100,
        "total_forecast": df["Forecast_Spend"].sum(),
        "total_actual": df["Actual_Spend"].sum(),
    }

before = _kpis(latest, "Before")
after = _kpis(modified, "After")

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Total |Error| Before",
          f"\u00a3{before['total_error']/1e6:,.1f}M")
k2.metric("Total |Error| After",
          f"\u00a3{after['total_error']/1e6:,.1f}M",
          delta=f"-\u00a3{recovered_error/1e6:,.1f}M",
          delta_color="normal")
k3.metric("Failure Rate Before", f"{before['fail_rate']:.1f}%")
k4.metric("Failure Rate After", f"{after['fail_rate']:.1f}%",
          delta=f"{after['fail_rate'] - before['fail_rate']:+.1f}pp",
          delta_color="normal")
k5.metric("\u00a3 Recovered", f"\u00a3{recovered_error/1e6:,.1f}M")

st.divider()

# ---------------------------------------------------------------------------
# Forecast comparison chart
# ---------------------------------------------------------------------------
st.markdown("### 2026 forecast band — before vs after intervention")

fc_before = build_forecast(latest, horizon_months=12)
fc_after = build_forecast(modified, horizon_months=12)

pf_before = roll_up(fc_before.portfolio, freq="M")
pf_after = roll_up(fc_after.portfolio, freq="M")

fig = go.Figure()

# Before — band
fig.add_trace(go.Scatter(
    x=pf_before["period_ts"], y=pf_before["p90"],
    line=dict(width=0), showlegend=False, hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=pf_before["period_ts"], y=pf_before["p10"],
    line=dict(width=0), fill="tonexty",
    fillcolor="rgba(215, 38, 56, 0.1)", name="Before P10\u2013P90",
))
fig.add_trace(go.Scatter(
    x=pf_before["period_ts"], y=pf_before["p50"],
    mode="lines+markers", line=dict(color=RR_RED, width=2, dash="dash"),
    name="Before P50",
))

# After — band
fig.add_trace(go.Scatter(
    x=pf_after["period_ts"], y=pf_after["p90"],
    line=dict(width=0), showlegend=False, hoverinfo="skip",
))
fig.add_trace(go.Scatter(
    x=pf_after["period_ts"], y=pf_after["p10"],
    line=dict(width=0), fill="tonexty",
    fillcolor="rgba(46, 139, 87, 0.1)", name="After P10\u2013P90",
))
fig.add_trace(go.Scatter(
    x=pf_after["period_ts"], y=pf_after["p50"],
    mode="lines+markers", line=dict(color=RR_GREEN, width=3),
    name="After P50",
))

fig.update_layout(
    height=480, margin=dict(l=10, r=10, t=20, b=10),
    hovermode="x unified",
    legend=dict(orientation="h", y=-0.15),
    plot_bgcolor="white",
    yaxis_title="\u00a3 spend",
)
fig.update_yaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
fig.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

# Summary
col_a, col_b, col_c = st.columns(3)
col_a.metric("Before P50 (annual)",
             f"\u00a3{pf_before['p50'].sum()/1e6:,.1f}M")
col_b.metric("After P50 (annual)",
             f"\u00a3{pf_after['p50'].sum()/1e6:,.1f}M",
             delta=f"\u00a3{(pf_after['p50'].sum()-pf_before['p50'].sum())/1e6:+,.1f}M")
col_c.metric("Band narrowing",
             f"\u00a3{((pf_before['p90'].sum()-pf_before['p10'].sum()) - (pf_after['p90'].sum()-pf_after['p10'].sum()))/1e6:,.1f}M",
             help="Reduction in P90\u2013P10 spread")

st.divider()

# ---------------------------------------------------------------------------
# Impact on the target entity
# ---------------------------------------------------------------------------
st.markdown(f"### Impact on **{target}**")

target_before = latest[latest[cfg["target_col"]] == target]
target_after = modified[modified[cfg["target_col"]] == target]

tc1, tc2, tc3, tc4 = st.columns(4)
tc1.metric("Error before",
           f"\u00a3{target_before['Absolute_Error'].sum()/1e6:,.2f}M")
tc2.metric("Error after",
           f"\u00a3{target_after['Absolute_Error'].sum()/1e6:,.2f}M",
           delta=f"-{reduction_pct*100:.0f}%")
tc3.metric("Fail rate before",
           f"{target_before['Forecast_Failed_Flag'].mean()*100:.1f}%")
tc4.metric("Fail rate after",
           f"{target_after['Forecast_Failed_Flag'].mean()*100:.1f}%")

st.caption(
    f"This simulation assumes a **{reduction_pct*100:.0f}%** reduction in forecast error "
    f"for {cfg['target_col'].replace('_', ' ')} = **{target}** based on the "
    f"'{intervention}' intervention. Actual results depend on implementation."
)
