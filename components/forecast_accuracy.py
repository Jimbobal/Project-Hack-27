"""
Forecast Accuracy analytics — per-driver linear regression predictions.

Adapts the attached app.py methodology: for each driver (Supplier_ID,
Contract_Type, Programme_ID), fit a LinearRegression of Actual_Spend on
Forecast_Spend per entity, then compare predicted vs actual to quantify
which driver class contributes the most systemic forecast error.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import streamlit as st
from sklearn.linear_model import LinearRegression


DRIVERS = {
    "Supplier":   "Supplier_ID",
    "Contract":   "Contract_Type",
    "Programme":  "Programme_ID",
}


@st.cache_data(show_spinner="Fitting per-entity regressions…")
def _fit_driver(latest: pd.DataFrame, driver_col: str) -> pd.DataFrame:
    """
    For every entity in *driver_col*, fit Forecast_Spend → Actual_Spend
    using Jan–Nov data (matching attached file's holdout logic), then
    predict across all periods.

    Returns a DataFrame with columns:
        Forecast_Period, <driver_col>, Forecast_Spend, Actual_Spend,
        Predicted_Actual_Spend, slope, intercept, r2, residual_std
    """
    df = latest.copy()
    df["Forecast_Period"] = df["period"].dt.to_timestamp().dt.strftime("%Y-%m")

    agg = (
        df.groupby(["Forecast_Period", driver_col])
        .agg(Forecast_Spend=("Forecast_Spend", "sum"),
             Actual_Spend=("Actual_Spend", "sum"))
        .reset_index()
    )

    entities = agg[driver_col].unique()
    rows = []

    for entity in entities:
        edf = agg[agg[driver_col] == entity].copy()

        # Train on all periods except the last (mirrors "!= 2025-12" logic)
        last_period = edf["Forecast_Period"].max()
        train = edf[edf["Forecast_Period"] != last_period]

        if len(train) < 2 or train["Forecast_Spend"].std() == 0:
            continue

        X_train = train[["Forecast_Spend"]]
        y_train = train["Actual_Spend"]

        model = LinearRegression().fit(X_train, y_train)
        r2 = model.score(X_train, y_train)

        # Residual std from training set for confidence bands
        train_pred = model.predict(X_train)
        residual_std = float(np.std(y_train.values - train_pred, ddof=1)) if len(train) > 2 else 0.0

        # Predict on all periods
        edf["Predicted_Actual_Spend"] = model.predict(edf[["Forecast_Spend"]])
        edf["slope"] = model.coef_[0]
        edf["intercept"] = model.intercept_
        edf["r2"] = r2
        edf["residual_std"] = residual_std
        edf["is_holdout"] = edf["Forecast_Period"] == last_period
        rows.append(edf)

    if not rows:
        return pd.DataFrame()

    return pd.concat(rows, ignore_index=True)


def fit_supplier(latest: pd.DataFrame) -> pd.DataFrame:
    return _fit_driver(latest, "Supplier_ID")


def fit_contract(latest: pd.DataFrame) -> pd.DataFrame:
    return _fit_driver(latest, "Contract_Type")


def fit_programme(latest: pd.DataFrame) -> pd.DataFrame:
    return _fit_driver(latest, "Programme_ID")


@st.cache_data(show_spinner="Computing driver impact…")
def driver_impact(latest: pd.DataFrame) -> pd.DataFrame:
    """
    Total absolute prediction error for each driver class.
    Returns DataFrame with columns: driver, total_abs_error, mean_abs_error, r2_mean
    """
    results = []
    for label, col in DRIVERS.items():
        pred = _fit_driver(latest, col)
        if pred.empty:
            continue
        pred["abs_error"] = (pred["Actual_Spend"] - pred["Predicted_Actual_Spend"]).abs()
        results.append({
            "driver": label,
            "total_abs_error": pred["abs_error"].sum(),
            "mean_abs_error": pred["abs_error"].mean(),
            "r2_mean": pred["r2"].mean(),
        })
    return pd.DataFrame(results).sort_values("total_abs_error", ascending=False).reset_index(drop=True)


@st.cache_data
def entity_drilldown(latest: pd.DataFrame, driver_col: str, top_n: int = 10) -> pd.DataFrame:
    """
    Top-N entities within a driver ranked by absolute prediction error.
    """
    pred = _fit_driver(latest, driver_col)
    if pred.empty:
        return pd.DataFrame()
    pred["abs_error"] = (pred["Actual_Spend"] - pred["Predicted_Actual_Spend"]).abs()
    return (
        pred.groupby(driver_col)
        .agg(total_abs_error=("abs_error", "sum"),
             mean_r2=("r2", "first"),
             periods=("Forecast_Period", "nunique"))
        .reset_index()
        .sort_values("total_abs_error", ascending=False)
        .head(top_n)
        .reset_index(drop=True)
    )
