"""
Methodology — documents the modelling stack for transparency & judging.
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(page_title="Methodology — Forecast Fade Radar",
                   page_icon="📊", layout="wide")

st.sidebar.image("assets/fade_radar_logo.png", width=200)

st.markdown("## 📊 Methodology")
st.caption("How the Forecast Fade Radar works — fully transparent stack.")

st.markdown("""
### Three pillars

**1 · Predict — confidence-banded 2026 forecast**

- **Seasonal baseline** per (supplier, commodity, programme) using 2025 monthly profile.
- **Damped trend** — linear slope across 2025 clipped to a reasonable growth band.
- **Monte Carlo residual bootstrap** (300 simulations) using supplier-specific residual
  volatility, widened by **profile-aware multipliers**:

| Profile | Volatility multiplier |
|---|---|
| Stable | 0.6× |
| Optimistic | 1.2× |
| Late Spender | 1.5× |
| Volatile | 1.8× |
| Chronic Fade | 2.2× |

- Roll-ups (programme / portfolio) aggregate **simulation draws before taking quantiles**
  — summing P90s overstates uncertainty; we sum draws then quantile.

**2 · Explain — driver attribution**

- **Waterfall decomposition** of portfolio variance into top-N named drivers (supplier,
  programme, commodity or contract type).
- **Fade signature** — error binned by days-before-period, showing how uncertainty
  compresses as the spend period approaches.
- **Optional SHAP layer** — LightGBM gradient-boosted regression trained on revision
  history + supplier / programme features, with SHAP values surfaced as feature drivers.

**3 · Prescribe — ranked intervention queue**

- A library of transparent, data-driven rules. Each rule pairs a **signal** with an
  **action** mapped to one of four levers:
  - **Commercial** — contract clauses, migration, rebates
  - **Supplier** — escalation, dual-source, PIP
  - **Portfolio** — envelope reallocation, ringfence changes
  - **Governance** — scope freeze, forecast cadence, data quality

- Recovery estimates apply a **conservative multiplier** to the fade contribution the
  rule addresses (e.g. 55% for Chronic-Fade + T&M migration, 30% for scope-freeze).

---

### LLM narrative layer

- **Anthropic Claude Haiku** (`claude-haiku-4-5-20251001`) generates the CFO briefing
  and Q&A answers.
- Fallback chain: Anthropic → OpenAI `gpt-4o-mini` → deterministic template. The demo
  never breaks.
- The LLM receives a **strict JSON context** derived from the provided dataset only.
  It cannot invent figures.

---

### Data sources

All from the Rolls-Royce supply-chain dummy dataset (no external data):

- `Forecast_Data` — forecast vs actual per (programme, supplier, commodity, period,
  revision)
- `Supplier_Attributes` — profile, OTIF, lead time, quality, strategic flag, contract type
- `Programme_Attributes` — phase, delivery risk, scope churn, change impact
- `Programme_Budget` — programme-level budget
- `Portfolio_Funding_Envelope` — monthly envelope, ringfenced, flexible, CFO target

---

### Caveats

- 2026 forecast is a **statistical extrapolation**, not a commercial plan. It assumes
  supplier behaviour holds constant. Interventions listed in the queue are designed
  precisely to break that assumption.
- Recovery £ figures are **engineering estimates** to help prioritise, not commitments.
  Every action requires commercial and delivery review before execution.
- Supplier profile labels are provided with the dataset. In production this would be
  derived from behaviour (clustering on fade signature + revision drift).
""")
