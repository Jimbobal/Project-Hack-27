"""
Ask the Forecast — free-text Q&A grounded in the portfolio data.

Uses Anthropic Claude (Haiku) by default, OpenAI as fallback, deterministic
template if neither is configured. Context is strictly limited to the
provided dataset.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from components.data_loader import (
    load_raw, build_fact, build_latest,
    supplier_league, programme_view,
)
from components.prescriptive import build_intervention_queue
from components.llm_narrative import ask_the_forecast

st.set_page_config(page_title="Ask the Forecast — Forecast Fade Radar",
                   page_icon="💬", layout="wide")

st.markdown("## 💬 Ask the Forecast")
st.caption("Ask any question of the 2025 actuals and 2026 projection — answers are "
           "grounded in the provided dataset only.")

raw = load_raw()
fact = build_fact(raw)
latest = build_latest(fact)

# -----------------------------------------------------------------------
# Build a compact JSON context for the LLM
# -----------------------------------------------------------------------
@st.cache_data
def build_context(_latest: pd.DataFrame, _fact: pd.DataFrame) -> dict:
    league = supplier_league(_latest).head(10)
    progs = programme_view(_latest)
    queue = build_intervention_queue(_latest, top_n=10)
    return {
        "portfolio": {
            "forecast_gbp_m": round(_latest["Forecast_Spend"].sum() / 1e6, 1),
            "actual_gbp_m": round(_latest["Actual_Spend"].sum() / 1e6, 1),
            "abs_error_gbp_m": round(_latest["Absolute_Error"].sum() / 1e6, 1),
            "fail_rate_pct": round(_latest["Forecast_Failed_Flag"].mean() * 100, 1),
        },
        "top_suppliers": league[[
            "Supplier_ID", "Supplier_Profile", "Contract_Type",
            "total_forecast", "total_abs_error", "fail_rate"
        ]].to_dict(orient="records"),
        "programmes": progs.to_dict(orient="records"),
        "top_interventions": (
            queue[["target", "lever", "signal", "action", "recovery_gbp"]]
            .to_dict(orient="records") if not queue.empty else []
        ),
    }


ctx = build_context(latest, fact)

# -----------------------------------------------------------------------
# Suggested prompts
# -----------------------------------------------------------------------
st.markdown("##### Try a suggested question:")
suggestions = [
    "Which three suppliers are causing the biggest forecast fade, and why?",
    "Where is spend most likely to overshoot envelope in 2026?",
    "What action would recover the most £ in the next 60 days?",
    "Which programmes have the highest scope-churn risk?",
    "Why is P003's variance so much higher than P002's?",
]
cols = st.columns(len(suggestions))
chosen = None
for i, s in enumerate(suggestions):
    if cols[i].button(s, use_container_width=True):
        chosen = s

# -----------------------------------------------------------------------
# Free-text input
# -----------------------------------------------------------------------
question = st.text_area(
    "Or type your own question:",
    value=chosen or "",
    height=100,
    placeholder="e.g. Which T&M suppliers should we migrate to Fixed Price first?",
)

if st.button("Ask", type="primary", disabled=not question.strip()):
    with st.spinner("Thinking…"):
        answer = ask_the_forecast(question.strip(), ctx)
    st.markdown("#### Answer")
    st.markdown(answer)

# -----------------------------------------------------------------------
# Context transparency
# -----------------------------------------------------------------------
with st.expander("🔍 What data does the assistant see?"):
    st.caption(
        "The assistant only sees the JSON below, built from the provided dataset. "
        "It cannot invent figures or reach outside this context."
    )
    st.json(ctx)
