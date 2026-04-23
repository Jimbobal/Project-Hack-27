"""
Cohort fade analytics — behavioural breakdowns by Supplier Profile,
Region, Payment Terms, and Programme Phase.

Adapts the fade_pipeline + cohort_analysis logic from the attached files:
collapses revisions into series-level data, then aggregates fade metrics
by each cohort dimension.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

SERIES_KEYS = ["Programme_ID", "Commodity", "Supplier_ID", "Forecast_Period"]

COHORT_DIMENSIONS = {
    "Supplier Profile":  "Supplier_Profile",
    "Region":            "Region",
    "Payment Terms":     "Payment_Terms",
    "Programme Phase":   "Programme_Phase",
}


@st.cache_data(show_spinner="Building series-level data…")
def _build_series(fact: pd.DataFrame) -> pd.DataFrame:
    """Collapse revision-level rows into one row per forecast series."""
    ordered = fact.sort_values("Revision_Number")

    series = ordered.groupby(SERIES_KEYS, as_index=False).agg(
        first_forecast=pd.NamedAgg(column="Forecast_Spend", aggfunc="first"),
        final_forecast=pd.NamedAgg(column="Forecast_Spend", aggfunc="last"),
        actual=pd.NamedAgg(column="Actual_Spend", aggfunc="last"),
        abs_error=pd.NamedAgg(column="Absolute_Error", aggfunc="last"),
        variance=pd.NamedAgg(column="Variance", aggfunc="last"),
        forecast_failed=pd.NamedAgg(column="Forecast_Failed_Flag", aggfunc="last"),
    )

    series["fade_abs"] = series["first_forecast"] - series["final_forecast"]
    series["fade_pct"] = series["fade_abs"] / series["first_forecast"].where(
        series["first_forecast"] != 0
    )

    # Carry forward the attribute columns needed for cohort grouping
    attr_cols = ["Supplier_Profile", "Region", "Payment_Terms", "Programme_Phase"]
    existing = [c for c in attr_cols if c in fact.columns]
    if existing:
        attrs = (
            ordered.groupby(SERIES_KEYS, as_index=False)[existing]
            .first()
        )
        series = series.merge(attrs, on=SERIES_KEYS, how="left")

    return series


@st.cache_data(show_spinner="Aggregating cohort metrics…")
def aggregate_cohort(fact: pd.DataFrame, dimension_col: str) -> pd.DataFrame:
    """
    Aggregate fade + forecast-accuracy metrics by a cohort dimension.

    Returns DataFrame sorted by fade_abs_gbp descending with columns:
        <dimension>, series_count, first_forecast_gbp, final_forecast_gbp,
        actual_gbp, fade_abs_gbp, fade_pct, mean_abs_error_gbp,
        median_abs_error_gbp, mape_pct, forecast_bias_gbp, failure_rate
    """
    series = _build_series(fact)

    if dimension_col not in series.columns:
        return pd.DataFrame()

    grouped = series.groupby(dimension_col, as_index=False).agg(
        series_count=pd.NamedAgg(column="first_forecast", aggfunc="size"),
        first_forecast_gbp=pd.NamedAgg(column="first_forecast", aggfunc="sum"),
        final_forecast_gbp=pd.NamedAgg(column="final_forecast", aggfunc="sum"),
        actual_gbp=pd.NamedAgg(column="actual", aggfunc="sum"),
        abs_error_sum=pd.NamedAgg(column="abs_error", aggfunc="sum"),
        mean_abs_error_gbp=pd.NamedAgg(column="abs_error", aggfunc="mean"),
        median_abs_error_gbp=pd.NamedAgg(column="abs_error", aggfunc="median"),
        forecast_bias_gbp=pd.NamedAgg(column="variance", aggfunc="mean"),
        failure_rate=pd.NamedAgg(column="forecast_failed", aggfunc="mean"),
    )

    grouped["fade_abs_gbp"] = (
        grouped["first_forecast_gbp"] - grouped["final_forecast_gbp"]
    )
    grouped["fade_pct"] = grouped["fade_abs_gbp"] / grouped[
        "first_forecast_gbp"
    ].where(grouped["first_forecast_gbp"] != 0)
    grouped["mape_pct"] = grouped["abs_error_sum"] / grouped["actual_gbp"].where(
        grouped["actual_gbp"] != 0
    )

    grouped = grouped.drop(columns=["abs_error_sum"])

    return grouped.sort_values("fade_abs_gbp", ascending=False).reset_index(drop=True)
