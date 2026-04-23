"""
Forecast Accuracy — predictions vs actuals with driver-level error attribution.

Per-driver linear regression (supplier, contract, programme) shows which
dimension contributes the most systemic forecast error, with drill-down
into individual entities.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from components.data_loader import load_raw
from components.forecast_accuracy import (
    fit_supplier, fit_contract, fit_programme,
    driver_impact, entity_drilldown, DRIVERS,
)


st.markdown("## \U0001f4e1 Forecast Accuracy")
st.caption(
    "How well does each driver predict actual spend? "
    "Identify systemic misses by supplier, contract type, or programme."
)

# -------------------------------------------------------------------
# Data
# -------------------------------------------------------------------
raw = load_raw()

# -------------------------------------------------------------------
# 1. Predictions vs Actuals chart
# -------------------------------------------------------------------
st.markdown("### Predictions vs Actuals")

FIT_FNS = {
    "Supplier":  fit_supplier,
    "Contract":  fit_contract,
    "Programme": fit_programme,
}

sel_driver = st.radio(
    "View by driver:", list(DRIVERS.keys()), horizontal=True, index=0,
)
driver_col = DRIVERS[sel_driver]
pred_df = FIT_FNS[sel_driver](raw)

if pred_df.empty:
    st.info("Not enough data to fit regressions for this driver.")
else:
    entities = sorted(pred_df[driver_col].unique())
    sel_entity = st.selectbox(f"Select {sel_driver.lower()}:", entities)

    edf = (
        pred_df[pred_df[driver_col] == sel_entity]
        .sort_values("Forecast_Period")
        .copy()
    )

    if edf.empty:
        st.info(f"No prediction data for {sel_entity}.")
    else:
        r_std = edf["residual_std"].iloc[0]
        edf["upper"] = edf["Predicted_Actual_Spend"] + 1.96 * r_std
        edf["lower"] = edf["Predicted_Actual_Spend"] - 1.96 * r_std
        edf["error"] = edf["Actual_Spend"] - edf["Predicted_Actual_Spend"]

        # Split into training periods (Jan-Nov) and holdout (Dec)
        train_df = edf[~edf["is_holdout"]].copy()
        holdout_df = edf[edf["is_holdout"]].copy()

        train_df["outside_band"] = (
            (train_df["Actual_Spend"] > train_df["upper"]) |
            (train_df["Actual_Spend"] < train_df["lower"])
        )

        fig = go.Figure()

        # Confidence band (all periods including Dec forecast)
        fig.add_trace(go.Scatter(
            x=edf["Forecast_Period"], y=edf["upper"],
            line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=edf["Forecast_Period"], y=edf["lower"],
            line=dict(width=0), fill="tonexty",
            fillcolor="rgba(30,39,97,0.12)",
            name="95% confidence band",
        ))

        # Predicted line (all periods)
        fig.add_trace(go.Scatter(
            x=edf["Forecast_Period"], y=edf["Predicted_Actual_Spend"],
            mode="lines+markers",
            line=dict(color="#1E2761", width=3),
            name="Predicted actual",
            customdata=edf[["Forecast_Spend", "error"]].values,
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Predicted: \u00a3%{y:,.0f}<br>"
                "Forecast spend: \u00a3%{customdata[0]:,.0f}<br>"
                "Error: \u00a3%{customdata[1]:+,.0f}<extra></extra>"
            ),
        ))

        # Actuals — only Jan-Nov (training), split in-band vs out-of-band
        in_band = train_df[~train_df["outside_band"]]
        out_band = train_df[train_df["outside_band"]]

        if not in_band.empty:
            fig.add_trace(go.Scatter(
                x=in_band["Forecast_Period"], y=in_band["Actual_Spend"],
                mode="markers",
                marker=dict(color="#2E8B57", size=10, symbol="diamond"),
                name="Actual (within band)",
                customdata=in_band[["Predicted_Actual_Spend", "error"]].values,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Actual: \u00a3%{y:,.0f}<br>"
                    "Predicted: \u00a3%{customdata[0]:,.0f}<br>"
                    "Error: \u00a3%{customdata[1]:+,.0f}<extra></extra>"
                ),
            ))

        if not out_band.empty:
            fig.add_trace(go.Scatter(
                x=out_band["Forecast_Period"], y=out_band["Actual_Spend"],
                mode="markers",
                marker=dict(color="#D72638", size=12, symbol="diamond",
                            line=dict(width=2, color="#D72638")),
                name="Actual (outside band)",
                customdata=out_band[["Predicted_Actual_Spend", "error"]].values,
                hovertemplate=(
                    "<b>%{x}</b><br>"
                    "Actual: \u00a3%{y:,.0f}<br>"
                    "Predicted: \u00a3%{customdata[0]:,.0f}<br>"
                    "Error: \u00a3%{customdata[1]:+,.0f}<br>"
                    "\u26a0 Outside confidence band<extra></extra>"
                ),
            ))

        # December forecast marker — distinct style
        if not holdout_df.empty:
            fig.add_trace(go.Scatter(
                x=holdout_df["Forecast_Period"],
                y=holdout_df["Predicted_Actual_Spend"],
                mode="markers",
                marker=dict(color="#FFB800", size=14, symbol="star",
                            line=dict(width=2, color="#1E2761")),
                name="Dec forecast (holdout)",
                hovertemplate=(
                    "<b>%{x} \u2014 Forecast</b><br>"
                    "Predicted: \u00a3%{y:,.0f}<br>"
                    "Model trained on Jan\u2013Nov only<extra></extra>"
                ),
            ))

        r2 = edf["r2"].iloc[0]
        fig.update_layout(
            height=460, margin=dict(l=10, r=10, t=30, b=10),
            plot_bgcolor="white",
            yaxis_title="\u00a3 spend",
            legend=dict(orientation="h", y=-0.18),
            hovermode="x unified",
            title_text=f"{sel_entity}  \u00b7  R\u00b2 = {r2:.3f}  \u00b7  Trained Jan\u2013Nov, forecasting Dec",
            title_font_size=14,
        )
        fig.update_yaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
        fig.update_xaxes(gridcolor="#EEE")
        st.plotly_chart(fig, use_container_width=True)

        # Headline: December forecast vs actual
        if not holdout_df.empty:
            dec = holdout_df.iloc[0]
            predicted = dec["Predicted_Actual_Spend"]
            actual = dec["Actual_Spend"]
            diff = actual - predicted
            diff_pct = diff / predicted * 100 if predicted else 0
            within = dec["lower"] <= actual <= dec["upper"]

            if within:
                verdict = ":green[within the 95% confidence band]"
            else:
                verdict = ":red[outside the 95% confidence band]"

            st.markdown(
                f"**December forecast for {sel_entity}:** "
                f"the model predicted **\u00a3{predicted/1e6:,.2f}M** based on the forecast spend. "
                f"Actual December spend was **\u00a3{actual/1e6:,.2f}M** "
                f"(**\u00a3{diff/1e6:+,.2f}M** / {diff_pct:+.1f}%), "
                f"{verdict}."
            )

        n_outside = train_df["outside_band"].sum() if not train_df.empty else 0
        if n_outside:
            st.caption(
                f":red[{n_outside} training period(s) fall outside the 95% confidence band] "
                f"\u2014 these are systemic misses worth investigating."
            )
        else:
            st.caption(
                ":green[All training-period actuals fall within the 95% confidence band] "
                "\u2014 this entity's forecast-to-actual relationship is stable."
            )

st.divider()

# -------------------------------------------------------------------
# 2. Driver impact ranking
# -------------------------------------------------------------------
st.markdown("### Driver impact ranking")

impact = driver_impact(raw)

if impact.empty:
    st.info("Not enough data to compute driver impact.")
else:
    top_driver = impact.iloc[0]["driver"]

    colours = [
        "#1E2761" if d == top_driver else "#CADCFC"
        for d in impact["driver"]
    ]

    fig_impact = go.Figure(go.Bar(
        y=impact["driver"],
        x=impact["total_abs_error"],
        orientation="h",
        marker_color=colours,
        text=impact["total_abs_error"].apply(lambda v: f"\u00a3{v/1e6:,.1f}M"),
        textposition="outside",
    ))

    fig_impact.add_annotation(
        x=impact.iloc[0]["total_abs_error"],
        y=top_driver,
        text="  \u25c0 highest impact",
        showarrow=False,
        font=dict(color="#D72638", size=12, weight="bold"),
        xanchor="left",
    )

    fig_impact.update_layout(
        height=260, margin=dict(l=10, r=120, t=10, b=10),
        plot_bgcolor="white",
        xaxis_title="Total absolute prediction error (\u00a3)",
        yaxis=dict(autorange="reversed"),
    )
    fig_impact.update_xaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
    st.plotly_chart(fig_impact, use_container_width=True)

    st.caption(
        f"**{top_driver}-level variance is the biggest source of forecast error this period.**"
    )

    # R-squared summary
    r2_text = " \u00b7 ".join(
        f"{row['driver']}: R\u00b2 = {row['r2_mean']:.3f}"
        for _, row in impact.iterrows()
    )
    st.caption(f"Model fit: {r2_text}")

st.divider()

# -------------------------------------------------------------------
# 3. Drill-down panel
# -------------------------------------------------------------------
st.markdown("### Drill-down by entity")

drill_driver = st.radio(
    "Drill into:", list(DRIVERS.keys()), horizontal=True, index=0,
    key="drill_radio",
)
drill_col = DRIVERS[drill_driver]

drill = entity_drilldown(raw, drill_col, top_n=10)

if drill.empty:
    st.info(f"Not enough data to drill down into {drill_driver.lower()}s.")
else:
    fig_drill = go.Figure(go.Bar(
        y=drill[drill_col],
        x=drill["total_abs_error"],
        orientation="h",
        marker_color="#FFB800",
        text=drill["total_abs_error"].apply(lambda v: f"\u00a3{v/1e6:,.1f}M"),
        textposition="outside",
    ))
    fig_drill.update_layout(
        height=max(280, len(drill) * 36),
        margin=dict(l=10, r=100, t=10, b=10),
        plot_bgcolor="white",
        xaxis_title="Total absolute prediction error (\u00a3)",
        yaxis=dict(autorange="reversed"),
    )
    fig_drill.update_xaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
    st.plotly_chart(fig_drill, use_container_width=True)

    st.caption(
        f"Top {len(drill)} {drill_driver.lower()}s ranked by cumulative prediction error. "
        f"Target these entities to reduce systemic forecast drift."
    )
