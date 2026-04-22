"""
Driver attribution — answers "why is spend higher or lower?"

Combines two approaches:
    1. Waterfall decomposition from the historical data — attributes absolute
       error to supplier/contract/programme buckets using actual - forecast.
    2. (Optional) LightGBM + SHAP for 2026-horizon forecasts, where we predict
       per-supplier forecast error and surface SHAP values as drivers.

For the 25-hour MVP, the waterfall is the primary mechanism — transparent,
defensible, and easy to explain to a CFO. SHAP layer is provided as a stub
that the team can switch on if time allows.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


def portfolio_waterfall(latest: pd.DataFrame,
                        top_n: int = 8,
                        mode: str = "supplier") -> pd.DataFrame:
    """
    Decompose portfolio forecast vs actual variance into top-N named drivers.

    mode in {"supplier", "programme", "commodity", "contract"}.
    Returns a DataFrame suitable for a waterfall chart with columns:
        label, contribution_gbp, direction, is_base
    """
    df = latest.copy()
    df["variance"] = df["Actual_Spend"] - df["Forecast_Spend"]  # +ve = overspend
    group_col = {
        "supplier": "Supplier_ID",
        "programme": "Programme_ID",
        "commodity": "Commodity",
        "contract": "Contract_Type",
    }[mode]

    agg = (df.groupby(group_col)["variance"].sum()
             .sort_values(key=lambda x: x.abs(), ascending=False))
    top = agg.head(top_n)
    rest = agg.iloc[top_n:].sum()

    total_forecast = df["Forecast_Spend"].sum()
    total_actual = df["Actual_Spend"].sum()

    rows = [{"label": "Forecast", "contribution_gbp": total_forecast,
             "is_base": True, "direction": "base"}]
    for name, val in top.items():
        rows.append({"label": str(name),
                     "contribution_gbp": float(val),
                     "is_base": False,
                     "direction": "over" if val > 0 else "under"})
    if abs(rest) > 0:
        rows.append({"label": "Other",
                     "contribution_gbp": float(rest),
                     "is_base": False,
                     "direction": "over" if rest > 0 else "under"})
    rows.append({"label": "Actual", "contribution_gbp": total_actual,
                 "is_base": True, "direction": "base"})
    return pd.DataFrame(rows)


def supplier_contribution(latest: pd.DataFrame,
                          filter_programme: str | None = None) -> pd.DataFrame:
    """Per-supplier contribution to total absolute error, with behavioural context."""
    df = latest.copy()
    if filter_programme:
        df = df[df["Programme_ID"] == filter_programme]
    df["over_under"] = df["Actual_Spend"] - df["Forecast_Spend"]
    out = (df.groupby(["Supplier_ID", "Supplier_Profile", "Contract_Type"])
             .agg(abs_error=("Absolute_Error", "sum"),
                  net_variance=("over_under", "sum"),
                  n_revisions=("Revision_Number", "max"),
                  fail_rate=("Forecast_Failed_Flag", "mean"),
                  avg_stability=("Forecast_Stability_Score", "mean"))
             .reset_index()
             .sort_values("abs_error", ascending=False))
    return out


def fade_curve(fact: pd.DataFrame) -> pd.DataFrame:
    """
    Forecast fade signature: for each days-before-period bucket, how wide is
    the forecast-vs-actual spread? This is the classic 'fade' chart.
    """
    df = fact.copy()
    df["days_bucket"] = pd.cut(
        df["Days_Before_Period"],
        bins=[-1, 30, 60, 90, 120, 150, 180, 365],
        labels=["<30d", "30-60d", "60-90d", "90-120d", "120-150d", "150-180d", ">180d"]
    )
    out = (df.groupby("days_bucket", observed=True)
             .agg(mean_error_pct=("Absolute_Error", "mean"),
                  n=("Forecast_Spend", "count"),
                  mean_stability=("Forecast_Stability_Score", "mean"))
             .reset_index())
    return out


# -----------------------------------------------------------------------------
# Optional: SHAP-based ML attribution (stub — switch on if time allows)
# -----------------------------------------------------------------------------
def train_error_model(fact: pd.DataFrame):
    """Train a LightGBM model predicting forecast error from supplier +
    programme + revision features. Returns (model, X, y, feature_names).
    """
    try:
        import lightgbm as lgb
    except ImportError:
        return None, None, None, None

    df = fact.copy()
    df["fail"] = df["Forecast_Failed_Flag"].fillna(0)
    features = [
        "OTIF_Pct", "Avg_Lead_Time_Days", "Quality_Incidents_YTD",
        "Revision_Number", "Days_Before_Period",
        "Commitment_Ratio", "PO_Count",
        "Programme_Change_Count", "Programme_Scope_Churn_Index",
        "Programme_Change_Impact_Index"
    ]
    cat_cols = ["Contract_Type", "Supplier_Profile", "Region",
                "Strategic_Flag", "New_Supplier_Flag", "Commodity",
                "Programme_Phase", "Delivery_Risk", "Confidence_Band"]
    X = df[features + cat_cols].copy()
    for c in cat_cols:
        X[c] = X[c].astype("category")
    y = df["Absolute_Error"].fillna(0)
    model = lgb.LGBMRegressor(n_estimators=150, learning_rate=0.05,
                              num_leaves=31, min_child_samples=20,
                              random_state=42, verbose=-1)
    model.fit(X, y, categorical_feature=cat_cols)
    return model, X, y, features + cat_cols


def shap_drivers(model, X, top_n: int = 10):
    """Return mean absolute SHAP value per feature."""
    try:
        import shap
    except ImportError:
        return None
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    importance = pd.DataFrame({
        "feature": X.columns,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0)
    }).sort_values("mean_abs_shap", ascending=False).head(top_n)
    return importance
