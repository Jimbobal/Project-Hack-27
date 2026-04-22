"""
CFO View — portfolio-level financial board view.

What a CFO wants to see:
    - Envelope vs Forecast vs Actual across the year
    - Ringfenced vs flexible envelope utilisation
    - Confidence target vs actual confidence delivered
    - 2026 projection with quarterly roll-up
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.data_loader import load_raw, build_fact, build_latest, monthly_portfolio
from components.forecast_engine import build_forecast, roll_up

st.set_page_config(page_title="CFO View — Forecast Fade Radar",
                   page_icon="💼", layout="wide")

st.markdown("## 💼 CFO View")
st.caption("Board-ready view of portfolio spend, envelope utilisation, and 2026 outlook.")

raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)
portfolio_m = monthly_portfolio(latest)

# -----------------------------------------------------------------------
# Granularity toggle
# -----------------------------------------------------------------------
freq_label = st.radio("Period granularity", ["Monthly", "Quarterly", "Yearly"],
                      horizontal=True, index=0)
freq = {"Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}[freq_label]

# -----------------------------------------------------------------------
# Envelope vs Forecast vs Actual
# -----------------------------------------------------------------------
st.markdown("### Envelope utilisation · Forecast vs Actual")

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
                  plot_bgcolor="white", yaxis_title="£ spend")
fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
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

# Coerce target to float — dataset sometimes stores it as a string like "80%".
raw_target = latest["CFO_Confidence_Target"].dropna().iloc[0] if "CFO_Confidence_Target" in latest.columns else 0.8
try:
    target = float(str(raw_target).strip().rstrip("%")) / (100 if "%" in str(raw_target) else 1)
except (ValueError, TypeError):
    target = 0.8
# Normalise: if value came in as e.g. 80 (meaning 80%) rather than 0.8, scale down
if target > 1:
    target = target / 100
st.info(
    f"**CFO confidence target: {target*100:.0f}%** "
    f"(rows currently meeting tolerance: **{100 - latest['Forecast_Failed_Flag'].mean()*100:.1f}%**). "
    f"Gap-to-target is the single biggest lever to move — driven primarily by Chronic Fade + T&M suppliers."
)

# -----------------------------------------------------------------------
# 2026 outlook
# -----------------------------------------------------------------------
st.markdown("### 2026 outlook (P10 · P50 · P90)")

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
    fillcolor="rgba(30,39,97,0.15)", name="P10–P90 band",
))
fig2.add_trace(go.Scatter(
    x=portfolio_fc["period_ts"], y=portfolio_fc["p50"],
    mode="lines+markers", line=dict(color="#1E2761", width=3),
    name="P50 central",
))
fig2.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                   hovermode="x unified",
                   legend=dict(orientation="h", y=-0.15),
                   plot_bgcolor="white", yaxis_title="£ spend")
fig2.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
fig2.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig2, use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("2026 P50", f"£{portfolio_fc['p50'].sum()/1e6:,.1f}M")
c2.metric("2026 P10 (upside)", f"£{portfolio_fc['p10'].sum()/1e6:,.1f}M")
c3.metric("2026 P90 (downside)", f"£{portfolio_fc['p90'].sum()/1e6:,.1f}M")
