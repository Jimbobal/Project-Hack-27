"""
Intervention Queue — ranked list of prescriptive actions with £ recovery.

This is the 'what to do next' page for a Programme Director.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.express as px

from components.data_loader import load_raw, build_fact, build_latest
from components.prescriptive import build_intervention_queue, RULES


st.markdown("## 🧭 Intervention Queue")
st.caption("Ranked prescriptive actions — estimated £ recovery and lever type.")

raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)

# -----------------------------------------------------------------------
# Filters
# -----------------------------------------------------------------------
col1, col2 = st.columns([1, 3])
with col1:
    top_n = st.slider("Show top N", 5, 30, 15)
with col2:
    levers = sorted({r["lever"] for r in RULES})
    lever_filter = st.multiselect("Filter by lever", levers, default=levers)

# -----------------------------------------------------------------------
# Queue
# -----------------------------------------------------------------------
queue = build_intervention_queue(latest, top_n=50)
if queue.empty:
    st.info("No interventions triggered.")
    st.stop()

queue = queue[queue["lever"].isin(lever_filter)].head(top_n).reset_index(drop=True)
queue["rank"] = queue.index + 1

# -----------------------------------------------------------------------
# Headline stats
# -----------------------------------------------------------------------
total_recovery = queue["recovery_gbp"].sum()
by_lever = queue.groupby("lever")["recovery_gbp"].sum().sort_values(ascending=False)

k1, k2, k3 = st.columns(3)
k1.metric("Total est. recovery", f"£{total_recovery/1e6:,.2f}M")
k2.metric("Actions queued", f"{len(queue)}")
k3.metric("Top lever", by_lever.index[0] if len(by_lever) else "—",
          delta=f"£{by_lever.iloc[0]/1e6:,.2f}M" if len(by_lever) else None)

# -----------------------------------------------------------------------
# Recovery by lever
# -----------------------------------------------------------------------
fig = px.bar(by_lever.reset_index(), x="lever", y="recovery_gbp",
             color="lever",
             color_discrete_map={
                 "Commercial": "#1E2761",
                 "Supplier": "#FFB800",
                 "Portfolio": "#4B9CD3",
                 "Governance": "#8B4789",
             },
             labels={"recovery_gbp": "Estimated recovery (£)", "lever": ""})
fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10),
                  plot_bgcolor="white", showlegend=False)
fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

# -----------------------------------------------------------------------
# Queue table
# -----------------------------------------------------------------------
st.markdown("### Ranked queue")

display = queue.copy()
display["recovery"] = display["recovery_gbp"].apply(
    lambda x: f"£{x/1e6:,.2f}M" if x >= 1e6 else f"£{x/1e3:,.0f}k"
)
display = display[["rank", "target", "lever", "rule", "signal", "action", "recovery"]]
display.columns = ["#", "Target", "Lever", "Rule", "Signal", "Action", "Recovery"]
st.dataframe(display, hide_index=True, use_container_width=True, height=500)

# Download button
csv_data = queue[["rank", "target", "lever", "rule", "signal", "action", "recovery_gbp"]].copy()
csv_data.columns = ["Rank", "Target", "Lever", "Rule", "Signal", "Action", "Recovery_GBP"]
st.download_button(
    "\u2b07 Download intervention queue (CSV)",
    data=csv_data.to_csv(index=False),
    file_name="intervention_queue.csv",
    mime="text/csv",
)

# -----------------------------------------------------------------------
# Rule library
# -----------------------------------------------------------------------
with st.expander("📖 Rule library — how the engine thinks"):
    st.markdown(
        "The prescriptive engine runs a library of transparent, data-driven rules. "
        "Each rule pairs a **signal** in the data with an **action** tied to a "
        "commercial / supplier / portfolio / governance lever. Recovery estimates "
        "apply a conservative multiplier to the historical fade contribution the "
        "rule addresses."
    )
    rule_df = pd.DataFrame([{"Rule": r["name"], "Lever": r["lever"]} for r in RULES])
    st.dataframe(rule_df, hide_index=True, use_container_width=True)
