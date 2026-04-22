# Forecast Fade Radar

**Project Hack 27 · Challenge 3 — Rolls-Royce Supply-Chain Forecasting**

A Streamlit web app that **predicts** 2026 supply-chain spend with confidence bands,
**explains** the drivers of forecast fade, and **prescribes** a ranked queue of
interventions with £ recovery estimates — all grounded in the provided dataset.

---

## Quick start

```bash
# 1. Create & activate a Python 3.11+ virtual environment
python -m venv .venv
source .venv/bin/activate      # (Windows: .venv\Scripts\activate)

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) configure LLM narrative
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# then edit secrets.toml and paste your ANTHROPIC_API_KEY

# 4. Run the app
streamlit run app.py
```

The app will launch at <http://localhost:8501>.

---

## App structure

```
forecast_fade_radar/
├── app.py                              # Programme Director Command Deck (landing)
├── pages/
│   ├── 2_CFO_View.py                   # Board-level envelope & 2026 outlook
│   ├── 3_Supplier_Intelligence.py      # Behavioural profiling & league
│   ├── 4_Forecast_Fade_Analytics.py    # Waterfall + fade curve + revision drift
│   ├── 5_Intervention_Queue.py         # Ranked prescriptive actions
│   ├── 6_Ask_the_Forecast.py           # Free-text LLM Q&A (grounded)
│   └── 7_Methodology.py                # Modelling stack documentation
├── components/
│   ├── data_loader.py                  # Load + join raw sheets → master tables
│   ├── forecast_engine.py              # 2026 Monte Carlo forecast with P10/50/90
│   ├── driver_attribution.py           # Waterfall + fade curve + optional SHAP
│   ├── prescriptive.py                 # Rule-based intervention queue
│   └── llm_narrative.py                # Anthropic/OpenAI narrative + fallback
├── data/
│   └── forecast_data.xlsx              # Provided Rolls-Royce dataset
├── .streamlit/
│   ├── config.toml                     # Theme (navy / ice / gold)
│   └── secrets.toml.example            # Template for LLM keys
├── requirements.txt
└── README.md
```

---

## Demo flow (5 minutes)

1. **Command Deck** (`app.py`) — KPI strip, 2026 forecast band, top-5 interventions.
2. **CFO View** — envelope utilisation + confidence target gap.
3. **Supplier Intelligence** — behavioural profile scatter (find the Chronic Fade cluster).
4. **Forecast Fade Analytics** — waterfall + fade curve ("*here's the why*").
5. **Intervention Queue** — ranked actions with £ recovery.
6. **Ask the Forecast** — live LLM Q&A (suggested prompts or freeform).
7. **Methodology** — for the judges.

---

## Modelling approach

See the in-app **Methodology** page for full detail. Summary:

- **Predict**: seasonal baseline × damped trend × Monte Carlo residual bootstrap, widened
  by profile-aware volatility multipliers (Chronic Fade 2.2× / Volatile 1.8× / Stable 0.6×).
- **Explain**: waterfall decomposition + fade-by-days-out curve + optional LightGBM +
  SHAP attribution.
- **Prescribe**: library of transparent rules mapped to four lever types (Commercial,
  Supplier, Portfolio, Governance), ranked by estimated £ recovery.

---

## Team

Built in 25 hours for Project Hack 27 — Challenge 3 ("Supply-Chain Spend Forecasting").
