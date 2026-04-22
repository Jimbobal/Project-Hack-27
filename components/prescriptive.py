"""
Prescriptive engine — ranked intervention queue.

Rules are data-driven and transparent. Each rule detects a pattern,
proposes an action tied to a lever category, and estimates £ recovery
from the historical forecast fade contribution.

Lever categories (mapped to Challenge 3 success criteria):
    - Commercial    : contract-type / clause-level actions
    - Supplier      : escalation / dual-source / replacement
    - Portfolio     : reallocation / ringfenced-vs-flex
    - Governance    : scope freeze / data-quality / cadence
"""

from __future__ import annotations

import pandas as pd


RULES = []


def rule(name: str, lever: str):
    """Decorator to register a rule."""
    def deco(fn):
        RULES.append({"name": name, "lever": lever, "fn": fn})
        return fn
    return deco


# ---------------- Individual rules ----------------

@rule("Chronic Fade + T&M contract → migrate to Fixed Price", "Commercial")
def rule_chronic_fade_tm(latest: pd.DataFrame) -> pd.DataFrame:
    mask = (latest["Supplier_Profile"] == "Chronic Fade") & \
           (latest["Contract_Type"] == "T&M")
    df = latest[mask].copy()
    if df.empty:
        return pd.DataFrame()
    agg = (df.groupby("Supplier_ID")
             .agg(abs_error=("Absolute_Error", "sum"),
                  forecast=("Forecast_Spend", "sum"))
             .reset_index())
    agg["recovery_gbp"] = agg["abs_error"] * 0.55  # conservative recovery ratio
    agg["target"] = agg["Supplier_ID"]
    agg["action"] = "Migrate T&M contract to Fixed Price with milestone gates"
    agg["signal"] = "Chronic Fade behaviour + T&M contract"
    return agg[["target", "signal", "action", "recovery_gbp", "abs_error"]]


@rule("Optimistic supplier + few revisions → increase revision cadence", "Governance")
def rule_optimistic_low_revisions(latest: pd.DataFrame) -> pd.DataFrame:
    mask = (latest["Supplier_Profile"] == "Optimistic")
    df = latest[mask].copy()
    if df.empty:
        return pd.DataFrame()
    df = df[df["Revision_Number"] <= 2]
    agg = (df.groupby("Supplier_ID")
             .agg(abs_error=("Absolute_Error", "sum"),
                  forecast=("Forecast_Spend", "sum"))
             .reset_index())
    agg["recovery_gbp"] = agg["abs_error"] * 0.35
    agg["target"] = agg["Supplier_ID"]
    agg["action"] = "Move to fortnightly forecast revisions; add commercial sign-off"
    agg["signal"] = "Optimistic profile + low revision cadence"
    return agg[["target", "signal", "action", "recovery_gbp", "abs_error"]]


@rule("Volatile strategic supplier → dual-source + QBR", "Supplier")
def rule_volatile_strategic(latest: pd.DataFrame) -> pd.DataFrame:
    mask = (latest["Supplier_Profile"] == "Volatile") & \
           (latest["Strategic_Flag"] == "Yes")
    df = latest[mask].copy()
    if df.empty:
        return pd.DataFrame()
    agg = (df.groupby(["Supplier_ID", "Commodity"])
             .agg(abs_error=("Absolute_Error", "sum"))
             .reset_index())
    agg["recovery_gbp"] = agg["abs_error"] * 0.45
    agg["target"] = agg["Supplier_ID"] + " (" + agg["Commodity"] + ")"
    agg["action"] = "Trigger QBR; dual-source the commodity"
    agg["signal"] = "Volatile + Strategic supplier"
    return agg[["target", "signal", "action", "recovery_gbp", "abs_error"]]


@rule("High scope churn programme → change-control freeze", "Governance")
def rule_scope_churn(latest: pd.DataFrame) -> pd.DataFrame:
    # Programme-level: average scope churn per month
    df = latest.groupby("Programme_ID").agg(
        avg_churn=("Programme_Scope_Churn_Index", "mean"),
        abs_error=("Absolute_Error", "sum")
    ).reset_index()
    median = df["avg_churn"].median()
    hits = df[df["avg_churn"] >= median * 1.5]
    if hits.empty:
        return pd.DataFrame()
    hits = hits.copy()
    hits["recovery_gbp"] = hits["abs_error"] * 0.30
    hits["target"] = hits["Programme_ID"]
    hits["action"] = "Convene Change Control Board; freeze non-critical scope for 60d"
    hits["signal"] = "Scope Churn Index ≥ 1.5× portfolio median"
    return hits[["target", "signal", "action", "recovery_gbp", "abs_error"]]


@rule("Low OTIF + quality incidents → performance plan", "Supplier")
def rule_otif_quality(latest: pd.DataFrame) -> pd.DataFrame:
    sup = latest.groupby("Supplier_ID").agg(
        avg_otif=("OTIF_Pct", "first"),
        q_incidents=("Quality_Incidents_YTD", "first"),
        abs_error=("Absolute_Error", "sum")
    ).reset_index()
    hits = sup[(sup["avg_otif"] < 90) & (sup["q_incidents"] >= 2)]
    if hits.empty:
        return pd.DataFrame()
    hits = hits.copy()
    hits["recovery_gbp"] = hits["abs_error"] * 0.25
    hits["target"] = hits["Supplier_ID"]
    hits["action"] = "Issue Performance Improvement Plan; withhold new PO issuance"
    hits["signal"] = "OTIF < 90% + ≥2 quality incidents YTD"
    return hits[["target", "signal", "action", "recovery_gbp", "abs_error"]]


@rule("Under-running programme freeing flexible envelope → reallocate", "Portfolio")
def rule_reallocate_flexible(latest: pd.DataFrame) -> pd.DataFrame:
    prog = latest.groupby("Programme_ID").agg(
        forecast=("Forecast_Spend", "sum"),
        actual=("Actual_Spend", "sum"),
        committed=("Committed_Spend", "sum")
    ).reset_index()
    prog["under_run"] = prog["forecast"] - prog["actual"]
    hits = prog[prog["under_run"] > prog["forecast"].median() * 0.1]
    if hits.empty:
        return pd.DataFrame()
    hits = hits.copy()
    hits["recovery_gbp"] = hits["under_run"].clip(lower=0) * 0.4
    hits["abs_error"] = hits["under_run"].abs()
    hits["target"] = hits["Programme_ID"]
    hits["action"] = "Reallocate unused flexible envelope to over-running programmes"
    hits["signal"] = "Actual < Forecast — free cash in envelope"
    return hits[["target", "signal", "action", "recovery_gbp", "abs_error"]]


# ---------------- Orchestration ----------------

def build_intervention_queue(latest: pd.DataFrame, top_n: int = 15) -> pd.DataFrame:
    """Run all rules, rank by estimated £ recovery."""
    all_rows = []
    for r in RULES:
        sub = r["fn"](latest)
        if sub is None or sub.empty:
            continue
        sub = sub.copy()
        sub["rule"] = r["name"]
        sub["lever"] = r["lever"]
        all_rows.append(sub)
    if not all_rows:
        return pd.DataFrame()
    out = pd.concat(all_rows, ignore_index=True)
    out = out.sort_values("recovery_gbp", ascending=False).head(top_n).reset_index(drop=True)
    out.insert(0, "rank", out.index + 1)
    return out
