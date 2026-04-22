"""
Data loading and cleaning for the Forecast Fade Radar.

All sheets from the Rolls-Royce dummy dataset are read once, cached in memory,
then joined into two master frames:
    - fact: one row per (programme, supplier, commodity, period, revision)
    - latest: one row per (programme, supplier, commodity, period) with latest revision

Period strings are normalised to pandas Period("M") for time arithmetic.
"""

from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "forecast_data.xlsx"


@st.cache_data(show_spinner="Loading dataset…")
def load_raw(path: str | Path = DATA_PATH) -> dict[str, pd.DataFrame]:
    """Read every sheet of the workbook into a dict of DataFrames."""
    xl = pd.ExcelFile(path)
    return {sheet: pd.read_excel(xl, sheet) for sheet in xl.sheet_names}


@st.cache_data(show_spinner="Building master fact table…")
def build_fact(raw: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Join Forecast_Data with supplier, programme and portfolio attributes."""
    fc = raw["Forecast_Data"].copy()
    sup = raw["Supplier_Attributes"].copy()
    prog = raw["Programme_Attributes"].copy()
    pbud = raw["Programme_Budget"].copy()
    env = raw["Portfolio_Funding_Envelope"].copy()

    fc["period"] = pd.PeriodIndex(fc["Forecast_Period"], freq="M")
    fc["forecast_version_date"] = pd.to_datetime(fc["Forecast_Version_Date"])
    fc["forecast_period_end_date"] = pd.to_datetime(fc["Forecast_Period_End_Date"])

    env["period"] = pd.PeriodIndex(env["Period"], freq="M")

    fact = (
        fc.merge(sup, on="Supplier_ID", how="left")
          .merge(prog, on="Programme_ID", how="left")
          .merge(pbud, on="Programme_ID", how="left")
          .merge(env[["period", "Total_Envelope_GBP", "Ringfenced_GBP",
                      "Flexible_GBP", "CFO_Confidence_Target"]],
                 on="period", how="left")
    )
    return fact


@st.cache_data
def build_latest(fact: pd.DataFrame) -> pd.DataFrame:
    """One row per (programme, supplier, commodity, period) — latest revision."""
    key = ["Programme_ID", "Supplier_ID", "Commodity", "period"]
    idx = fact.groupby(key)["Revision_Number"].idxmax()
    return fact.loc[idx].sort_values(key).reset_index(drop=True)


@st.cache_data
def monthly_portfolio(latest: pd.DataFrame) -> pd.DataFrame:
    """Portfolio roll-up by month (latest revision)."""
    agg = (latest.groupby("period")
                 .agg(forecast=("Forecast_Spend", "sum"),
                      actual=("Actual_Spend", "sum"),
                      committed=("Committed_Spend", "sum"),
                      envelope=("Total_Envelope_GBP", "first"),
                      ringfenced=("Ringfenced_GBP", "first"),
                      flexible=("Flexible_GBP", "first"),
                      failed_rows=("Forecast_Failed_Flag", "sum"),
                      total_rows=("Forecast_Failed_Flag", "count"))
                 .reset_index())
    agg["period_ts"] = agg["period"].dt.to_timestamp()
    agg["fail_rate"] = agg["failed_rows"] / agg["total_rows"]
    agg["variance_vs_envelope"] = agg["forecast"] - agg["envelope"]
    return agg


def aggregate_by(latest: pd.DataFrame, by: str = "M") -> pd.DataFrame:
    """Roll up to Monthly / Quarterly / Yearly. `by` in {'M','Q','Y'}."""
    df = latest.copy()
    df["period_ts"] = df["period"].dt.to_timestamp()
    if by == "M":
        df["bucket"] = df["period_ts"].dt.to_period("M").dt.to_timestamp()
    elif by == "Q":
        df["bucket"] = df["period_ts"].dt.to_period("Q").dt.to_timestamp()
    else:
        df["bucket"] = df["period_ts"].dt.to_period("Y").dt.to_timestamp()
    return (df.groupby("bucket")
              .agg(forecast=("Forecast_Spend", "sum"),
                   actual=("Actual_Spend", "sum"),
                   committed=("Committed_Spend", "sum"))
              .reset_index())


def fade_by_revision(fact: pd.DataFrame) -> pd.DataFrame:
    """How much does the forecast move across revisions? Portfolio-level fade."""
    return (fact.groupby("Revision_Number")
                .agg(rows=("Forecast_Spend", "size"),
                     mean_abs_change=("Forecast_Change", lambda x: x.abs().mean()),
                     mean_stability=("Forecast_Stability_Score", "mean"))
                .reset_index())


def supplier_league(latest: pd.DataFrame) -> pd.DataFrame:
    """Supplier league table by total absolute error (forecast fade contribution)."""
    return (latest.groupby(["Supplier_ID", "Supplier_Profile",
                            "Contract_Type", "Region", "Strategic_Flag"])
                  .agg(total_forecast=("Forecast_Spend", "sum"),
                       total_actual=("Actual_Spend", "sum"),
                       total_abs_error=("Absolute_Error", "sum"),
                       n_periods=("period", "nunique"),
                       fail_rate=("Forecast_Failed_Flag", "mean"),
                       avg_otif=("OTIF_Pct", "first"),
                       quality_incidents=("Quality_Incidents_YTD", "first"))
                  .reset_index()
                  .sort_values("total_abs_error", ascending=False))


def programme_view(latest: pd.DataFrame) -> pd.DataFrame:
    """One row per programme with key KPIs."""
    return (latest.groupby(["Programme_ID", "Programme_Phase", "Delivery_Risk",
                            "Programme_Value_GBP", "Annual_SupplyChain_Budget_GBP"])
                  .agg(total_forecast=("Forecast_Spend", "sum"),
                       total_actual=("Actual_Spend", "sum"),
                       total_abs_error=("Absolute_Error", "sum"),
                       fail_rate=("Forecast_Failed_Flag", "mean"),
                       avg_scope_churn=("Programme_Scope_Churn_Index", "mean"),
                       avg_change_impact=("Programme_Change_Impact_Index", "mean"))
                  .reset_index())
