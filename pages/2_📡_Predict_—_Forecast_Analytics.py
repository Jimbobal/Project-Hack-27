"""
Forecast Fade Analytics — the 'why' page.

Portfolio waterfall + fade curve + revision-by-revision drift.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.data_loader import load_raw, build_fact, build_latest, fade_by_revision
from components.driver_attribution import portfolio_waterfall, fade_curve
from components.cohort_analytics import aggregate_cohort, COHORT_DIMENSIONS


st.markdown("## 📐 Forecast Fade Analytics")
st.caption("Decompose variance. Explain the 'why' behind every £ of drift.")

raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)

# -----------------------------------------------------------------------
# Waterfall
# -----------------------------------------------------------------------
st.markdown("### Portfolio waterfall — forecast → actual")
mode = st.radio("Decompose by:", ["supplier", "programme", "commodity", "contract"],
                horizontal=True, index=0)
top_n = st.slider("Top N named drivers", 3, 15, 8)

wf = portfolio_waterfall(latest, top_n=top_n, mode=mode)

# Build Plotly waterfall figure from the decomposition.
measures = ["absolute"] + ["relative"] * (len(wf) - 2) + ["total"]
fig = go.Figure(go.Waterfall(
    orientation="v",
    measure=measures,
    x=wf["label"],
    y=wf["contribution_gbp"],
    text=[f"£{v/1e6:+,.1f}M" if not b else f"£{v/1e6:,.1f}M"
          for v, b in zip(wf["contribution_gbp"], wf["is_base"])],
    textposition="outside",
    connector={"line": {"color": "rgb(180,180,180)"}},
    increasing={"marker": {"color": "#E85D75"}},
    decreasing={"marker": {"color": "#2E8B57"}},
    totals={"marker": {"color": "#1E2761"}},
))
fig.update_layout(height=480, margin=dict(l=10, r=10, t=20, b=10),
                  plot_bgcolor="white", yaxis_title="£ variance",
                  showlegend=False)
fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
st.plotly_chart(fig, use_container_width=True)

st.caption(
    "🔴 Red bars = **overspend** vs forecast · 🟢 Green bars = **underspend** vs forecast · "
    "🔵 Blue = totals."
)

# -----------------------------------------------------------------------
# Fade curve — how error changes as we approach the spend period
# -----------------------------------------------------------------------
st.markdown("### Fade signature — error shrinks as period approaches")

fc_curve = fade_curve(fact)

fig2 = go.Figure()
fig2.add_trace(go.Bar(
    x=fc_curve["days_bucket"].astype(str),
    y=fc_curve["mean_error_pct"],
    marker_color="#1E2761",
    name="Mean |Error|",
    yaxis="y1",
))
fig2.add_trace(go.Scatter(
    x=fc_curve["days_bucket"].astype(str),
    y=fc_curve["mean_stability"],
    mode="lines+markers", line=dict(color="#FFB800", width=3),
    name="Mean stability score", yaxis="y2",
))
fig2.update_layout(
    height=400, margin=dict(l=10, r=10, t=10, b=10),
    plot_bgcolor="white",
    yaxis=dict(title="Mean |Error| (£)", tickprefix="£", tickformat=",.0f",
               gridcolor="#EEE"),
    yaxis2=dict(title="Stability score", overlaying="y", side="right",
                range=[0, 1]),
    legend=dict(orientation="h", y=-0.15),
    xaxis_title="Days before spend period",
)
st.plotly_chart(fig2, use_container_width=True)

st.caption(
    "This is the classic 'forecast fade' signature: the further out we are, "
    "the wider the error — and the lower the confidence. The goal of our "
    "prescriptive levers is to **compress this curve** by intervening early "
    "on the suppliers and programmes most responsible for the drift."
)

# -----------------------------------------------------------------------
# Revision drift
# -----------------------------------------------------------------------
st.markdown("### Revision-by-revision drift")

rev = fade_by_revision(fact)
fig3 = go.Figure(go.Bar(
    x=rev["Revision_Number"], y=rev["mean_abs_change"],
    marker_color="#CADCFC",
    text=rev["mean_abs_change"].apply(lambda x: f"£{x/1e3:,.0f}k"),
    textposition="outside",
))
fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                   plot_bgcolor="white",
                   xaxis_title="Revision number",
                   yaxis_title="Mean |forecast change|")
fig3.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
st.plotly_chart(fig3, use_container_width=True)

st.caption(
    "A well-behaved forecast system should show shrinking revision movements over "
    "time — each revision should carry less new information. If revisions late in "
    "the cycle still swing heavily, the baseline is structurally wrong."
)

# -----------------------------------------------------------------------
# Cohort fade breakdowns
# -----------------------------------------------------------------------
st.markdown("### Cohort fade breakdowns")

COHORT_COLOURS = {
    "Supplier Profile": "#1E2761",
    "Region":           "#FFB800",
    "Payment Terms":    "#2E8B57",
    "Programme Phase":  "#D72638",
}

fade_tab, median_tab = st.tabs([
    "\U0001f4c9 Total Fade + Failure Rate",
    "\U0001f4ca Median Error + Failure Rate",
])

def _cohort_chart(container, label, col, bar_x, bar_text_fn, x_title, chart_title):
    """Render one cohort chart inside the given Streamlit container."""
    cdf = aggregate_cohort(fact, col)
    if cdf.empty:
        container.info(f"No data available for {label}.")
        return

    bar_colour = COHORT_COLOURS.get(label, "#1E2761")
    fig_c = go.Figure()

    fig_c.add_trace(go.Bar(
        y=cdf[col],
        x=cdf[bar_x],
        orientation="h",
        marker_color=bar_colour,
        text=cdf[bar_x].apply(bar_text_fn),
        textposition="outside",
        name=x_title,
    ))

    fig_c.add_trace(go.Scatter(
        y=cdf[col],
        x=cdf["failure_rate"] * 100,
        mode="lines+markers+text",
        marker=dict(color="#D72638", size=10),
        line=dict(color="#D72638", width=2, dash="dot"),
        text=cdf["failure_rate"].apply(lambda v: f"{v*100:.0f}%"),
        textposition="middle right",
        name="Failure rate (%)",
        xaxis="x2",
    ))

    fig_c.update_layout(
        title=chart_title,
        title_font_size=14,
        height=max(300, len(cdf) * 55),
        margin=dict(l=10, r=10, t=40, b=40),
        plot_bgcolor="white",
        yaxis=dict(autorange="reversed"),
        xaxis=dict(
            title=x_title,
            tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE",
            side="bottom",
        ),
        xaxis2=dict(
            title="Failure rate (%)",
            ticksuffix="%",
            overlaying="x",
            side="top",
            gridcolor="rgba(0,0,0,0)",
            range=[0, max(cdf["failure_rate"].max() * 100 * 1.3, 10)],
        ),
        legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
        hovermode="y unified",
    )
    container.plotly_chart(fig_c, use_container_width=True)


with fade_tab:
    st.caption(
        "Bars show total absolute fade (\u00a3) per cohort \u2014 "
        "the bigger the bar, the more that cohort\u2019s forecasts shrink "
        "between first and final revision. Red dotted line = failure rate."
    )
    for label, col in COHORT_DIMENSIONS.items():
        _cohort_chart(
            st, label, col,
            bar_x="fade_abs_gbp",
            bar_text_fn=lambda v: f"\u00a3{v/1e6:,.1f}M",
            x_title="Total fade (\u00a3)",
            chart_title=f"Forecast fade by {label}",
        )

with median_tab:
    st.caption(
        "Bars show the median absolute forecast error (\u00a3) per cohort \u2014 "
        "a robust measure of typical error size, resistant to outliers. "
        "Red dotted line = failure rate."
    )
    for label, col in COHORT_DIMENSIONS.items():
        _cohort_chart(
            st, label, col,
            bar_x="median_abs_error_gbp",
            bar_text_fn=lambda v: f"\u00a3{v/1e6:,.2f}M" if v >= 1e6 else f"\u00a3{v/1e3:,.0f}k",
            x_title="Median |error| (\u00a3)",
            chart_title=f"Median forecast error by {label}",
        )
