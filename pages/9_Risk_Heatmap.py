"""
Risk Heatmap — Programme vs Supplier risk matrix.

Instantly shows where the hotspots are across the portfolio.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from components.data_loader import load_raw, build_fact, build_latest

st.set_page_config(page_title="Risk Heatmap — Fade Radar",
                   page_icon="\U0001f525", layout="wide")

st.markdown("## \U0001f525 Risk Heatmap")
st.caption("Programme vs Supplier risk matrix — instantly spot the hotspots.")

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
# Filters
# ---------------------------------------------------------------------------
f1, f2 = st.columns(2)
with f1:
    profiles = sorted(latest["Supplier_Profile"].dropna().unique())
    profile_filter = st.multiselect("Supplier profile", profiles, default=profiles)
with f2:
    contracts = sorted(latest["Contract_Type"].dropna().unique())
    contract_filter = st.multiselect("Contract type", contracts, default=contracts)

filtered = latest[
    latest["Supplier_Profile"].isin(profile_filter)
    & latest["Contract_Type"].isin(contract_filter)
]

# ---------------------------------------------------------------------------
# Metric toggle
# ---------------------------------------------------------------------------
metric = st.radio(
    "Heatmap metric",
    ["Absolute Error (\u00a3)", "Failure Rate (%)", "Forecast Variance (%)"],
    horizontal=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Build pivot
# ---------------------------------------------------------------------------
if metric == "Absolute Error (\u00a3)":
    pivot = filtered.pivot_table(
        index="Programme_ID", columns="Supplier_ID",
        values="Absolute_Error", aggfunc="sum", fill_value=0,
    )
    fmt = "\u00a3,.0f"
    hover_suffix = ""
elif metric == "Failure Rate (%)":
    pivot = filtered.pivot_table(
        index="Programme_ID", columns="Supplier_ID",
        values="Forecast_Failed_Flag", aggfunc="mean", fill_value=0,
    ) * 100
    fmt = ".1f"
    hover_suffix = "%"
else:
    # Variance % = (actual - forecast) / forecast
    temp = filtered.copy()
    temp["variance_pct"] = (
        (temp["Actual_Spend"] - temp["Forecast_Spend"])
        / temp["Forecast_Spend"].replace(0, np.nan) * 100
    )
    pivot = temp.pivot_table(
        index="Programme_ID", columns="Supplier_ID",
        values="variance_pct", aggfunc="mean", fill_value=0,
    )
    fmt = "+.1f"
    hover_suffix = "%"

# ---------------------------------------------------------------------------
# Heatmap
# ---------------------------------------------------------------------------
st.markdown("### Programme \u00d7 Supplier heatmap")

# Custom hover text
hover_text = []
for i, prog in enumerate(pivot.index):
    row = []
    for j, sup in enumerate(pivot.columns):
        val = pivot.iloc[i, j]
        if metric == "Absolute Error (\u00a3)":
            val_str = f"\u00a3{val:,.0f}"
        elif metric == "Failure Rate (%)":
            val_str = f"{val:.1f}%"
        else:
            val_str = f"{val:+.1f}%"
        row.append(f"Programme: {prog}<br>Supplier: {sup}<br>{metric}: {val_str}")
    hover_text.append(row)

colorscale = [[0, RR_GREEN], [0.5, RR_GOLD], [1, RR_RED]]

fig = go.Figure(data=go.Heatmap(
    z=pivot.values,
    x=pivot.columns.tolist(),
    y=pivot.index.tolist(),
    colorscale=colorscale,
    hovertext=hover_text,
    hoverinfo="text",
    colorbar=dict(title=metric.split("(")[0].strip()),
))

fig.update_layout(
    height=max(350, len(pivot.index) * 60 + 100),
    margin=dict(l=10, r=10, t=20, b=10),
    plot_bgcolor="white",
    xaxis_title="Supplier",
    yaxis_title="Programme",
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(fig, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Top 10 hotspots table
# ---------------------------------------------------------------------------
st.markdown("### Top 10 hotspots")

hotspots = filtered.groupby(["Programme_ID", "Supplier_ID"]).agg(
    abs_error=("Absolute_Error", "sum"),
    forecast=("Forecast_Spend", "sum"),
    actual=("Actual_Spend", "sum"),
    fail_rate=("Forecast_Failed_Flag", "mean"),
    profile=("Supplier_Profile", "first"),
    contract=("Contract_Type", "first"),
).reset_index()
hotspots["variance_pct"] = (
    (hotspots["actual"] - hotspots["forecast"])
    / hotspots["forecast"].replace(0, 1) * 100
)
hotspots["fail_rate_pct"] = hotspots["fail_rate"] * 100
hotspots = hotspots.sort_values("abs_error", ascending=False).head(10).reset_index(drop=True)
hotspots.insert(0, "rank", hotspots.index + 1)

display = hotspots[["rank", "Programme_ID", "Supplier_ID", "profile", "contract",
                     "forecast", "actual", "abs_error", "variance_pct",
                     "fail_rate_pct"]].copy()
display.columns = ["#", "Programme", "Supplier", "Profile", "Contract",
                    "Forecast (\u00a3)", "Actual (\u00a3)", "|Error| (\u00a3)",
                    "Variance %", "Fail %"]


def _fmt_gbp(val):
    if abs(val) >= 1e6:
        return f"\u00a3{val/1e6:,.1f}M"
    return f"\u00a3{val/1e3:,.0f}k"


styled = (display.style
          .format({
              "Forecast (\u00a3)": lambda x: _fmt_gbp(x),
              "Actual (\u00a3)": lambda x: _fmt_gbp(x),
              "|Error| (\u00a3)": lambda x: _fmt_gbp(x),
              "Variance %": lambda x: f"{x:+.1f}%",
              "Fail %": lambda x: f"{x:.1f}%",
          })
          .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 0
               else (f"color: {RR_GREEN}; font-weight: bold" if v < 0 else ""),
               subset=["Variance %"])
          .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 20
               else "", subset=["Fail %"]))
st.dataframe(styled, hide_index=True, use_container_width=True)

st.download_button(
    "\u2b07 Download hotspots (CSV)",
    data=display.to_csv(index=False),
    file_name="risk_hotspots.csv",
    mime="text/csv",
)
