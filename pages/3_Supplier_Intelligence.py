"""
Supplier Intelligence — behavioural profiling and league tables.

Answers: which suppliers are driving the fade, and what do they look like?
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from components.data_loader import load_raw, build_fact, build_latest, supplier_league
from components.driver_attribution import supplier_contribution

st.set_page_config(page_title="Supplier Intelligence — Forecast Fade Radar",
                   page_icon="🤝", layout="wide")

st.markdown("## 🤝 Supplier Intelligence")
st.caption("Behavioural profiling — who's driving the fade, and why.")

raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)

# -----------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------
left, right = st.columns(2)
with left:
    profile_filter = st.multiselect(
        "Supplier profile",
        sorted(latest["Supplier_Profile"].dropna().unique()),
        default=sorted(latest["Supplier_Profile"].dropna().unique()),
    )
with right:
    contract_filter = st.multiselect(
        "Contract type",
        sorted(latest["Contract_Type"].dropna().unique()),
        default=sorted(latest["Contract_Type"].dropna().unique()),
    )

filtered = latest[
    latest["Supplier_Profile"].isin(profile_filter)
    & latest["Contract_Type"].isin(contract_filter)
]

# -----------------------------------------------------------------------
# Supplier league table
# -----------------------------------------------------------------------
st.markdown("### Supplier league — ranked by forecast fade contribution")
league = supplier_league(filtered).head(20)
league_disp = league.copy()
league_disp["total_forecast"] = league_disp["total_forecast"].apply(lambda x: f"£{x/1e6:,.2f}M")
league_disp["total_actual"] = league_disp["total_actual"].apply(lambda x: f"£{x/1e6:,.2f}M")
league_disp["total_abs_error"] = league_disp["total_abs_error"].apply(lambda x: f"£{x/1e6:,.2f}M")
league_disp["fail_rate"] = (league_disp["fail_rate"] * 100).round(1).astype(str) + "%"
league_disp["avg_otif"] = league_disp["avg_otif"].round(1).astype(str) + "%"

league_disp.columns = [
    "Supplier", "Profile", "Contract", "Region", "Strategic",
    "Forecast", "Actual", "|Error|", "Periods", "Fail %",
    "OTIF %", "Quality Incidents"
]
st.dataframe(league_disp, hide_index=True, use_container_width=True, height=500)

# -----------------------------------------------------------------------
# Profile behaviour scatter
# -----------------------------------------------------------------------
st.markdown("### Profile behaviour map")
st.caption("Forecast fade vs forecast stability — each bubble is a supplier, "
           "sized by spend, coloured by profile.")

plot_df = (filtered.groupby(["Supplier_ID", "Supplier_Profile",
                             "Contract_Type", "Strategic_Flag"])
                   .agg(forecast=("Forecast_Spend", "sum"),
                        abs_error=("Absolute_Error", "sum"),
                        stability=("Forecast_Stability_Score", "mean"),
                        otif=("OTIF_Pct", "first"))
                   .reset_index())
plot_df["fade_pct"] = plot_df["abs_error"] / plot_df["forecast"].replace(0, 1) * 100

fig = px.scatter(
    plot_df, x="stability", y="fade_pct",
    size="forecast", color="Supplier_Profile",
    hover_data=["Supplier_ID", "Contract_Type", "Strategic_Flag", "otif"],
    color_discrete_map={
        "Stable": "#1E2761",
        "Optimistic": "#FFB800",
        "Volatile": "#E85D75",
        "Chronic Fade": "#8B0000",
        "Late Spender": "#4B9CD3",
    },
    labels={"stability": "Forecast stability score",
            "fade_pct": "Forecast fade % (|error| / forecast)"},
    height=500,
)
fig.update_layout(margin=dict(l=10, r=10, t=10, b=10),
                  plot_bgcolor="white",
                  legend=dict(orientation="h", y=-0.15))
fig.update_yaxes(ticksuffix="%", gridcolor="#EEE")
fig.update_xaxes(gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------
# Profile summary
# -----------------------------------------------------------------------
st.markdown("### Profile summary")

prof_sum = (filtered.groupby("Supplier_Profile")
                    .agg(n_suppliers=("Supplier_ID", "nunique"),
                         total_forecast=("Forecast_Spend", "sum"),
                         total_error=("Absolute_Error", "sum"),
                         fail_rate=("Forecast_Failed_Flag", "mean"))
                    .reset_index())
prof_sum["fade_pct"] = prof_sum["total_error"] / prof_sum["total_forecast"].replace(0, 1) * 100

c1, c2 = st.columns(2)
with c1:
    fig_p = px.bar(prof_sum.sort_values("total_error", ascending=True),
                   x="total_error", y="Supplier_Profile", orientation="h",
                   color="Supplier_Profile",
                   color_discrete_map={
                       "Stable": "#1E2761",
                       "Optimistic": "#FFB800",
                       "Volatile": "#E85D75",
                       "Chronic Fade": "#8B0000",
                       "Late Spender": "#4B9CD3",
                   },
                   labels={"total_error": "Total |Error| (£)",
                           "Supplier_Profile": ""})
    fig_p.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                        plot_bgcolor="white", showlegend=False)
    fig_p.update_xaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    st.plotly_chart(fig_p, use_container_width=True)
with c2:
    st.dataframe(
        prof_sum.assign(
            total_forecast=lambda d: d["total_forecast"].apply(lambda x: f"£{x/1e6:,.1f}M"),
            total_error=lambda d: d["total_error"].apply(lambda x: f"£{x/1e6:,.1f}M"),
            fail_rate=lambda d: (d["fail_rate"] * 100).round(1).astype(str) + "%",
            fade_pct=lambda d: d["fade_pct"].round(1).astype(str) + "%",
        ),
        hide_index=True, use_container_width=True,
    )
