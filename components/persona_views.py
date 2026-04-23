"""
Persona views for the Forecast Fade Radar Home page.

Four distinct dashboard layouts, one per persona:
    1. Programme Director — commit number + confidence
    2. CFO — trust the number + release flexible capital
    3. Commercial Manager — supplier/contract intervention this week
    4. Project Controls Lead — behaviour/data-quality fixes for better forecasting
"""

from __future__ import annotations

import os
import io
import re
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

from components.data_loader import (
    programme_view, supplier_league, monthly_portfolio,
    aggregate_by, fade_by_revision,
)
from components.forecast_engine import build_forecast, roll_up
from components.prescriptive import build_intervention_queue
from components.driver_attribution import (
    portfolio_waterfall, supplier_contribution, fade_curve,
)

# ---------------------------------------------------------------------------
# Rolls-Royce palette
# ---------------------------------------------------------------------------
RR_NAVY = "#1E2761"
RR_GOLD = "#FFB800"
RR_RED = "#D72638"
RR_GREEN = "#2E8B57"
RR_LIGHT_BG = "#F5F7FB"
RR_LIGHT_BLUE = "#CADCFC"


# ---------------------------------------------------------------------------
# ElevenLabs voice briefing
# ---------------------------------------------------------------------------
def _get_elevenlabs_key() -> str | None:
    try:
        return st.secrets.get("ELEVENLABS_API_KEY")
    except Exception:
        return os.environ.get("ELEVENLABS_API_KEY")


def _generate_voice(text: str, voice: str = "21m00Tcm4TlvDq8ikWAM") -> bytes | None:
    """Generate speech audio from text using ElevenLabs."""
    api_key = _get_elevenlabs_key()
    if not api_key:
        return None
    try:
        from elevenlabs.client import ElevenLabs
        client = ElevenLabs(api_key=api_key)
        audio_gen = client.text_to_speech.convert(
            text=text,
            voice_id=voice,
            model_id="eleven_multilingual_v2",
            output_format="mp3_44100_128",
        )
        # audio_gen is a generator of bytes chunks
        audio_bytes = b"".join(audio_gen)
        return audio_bytes
    except Exception as e:
        st.warning(f"Voice generation failed: {e}")
        return None


def _strip_markdown(text: str) -> str:
    """Remove markdown formatting and make numbers TTS-friendly."""
    # Strip markdown bold/italic
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Unicode symbols to spoken words
    text = text.replace('\u2014', ', ')
    text = text.replace('\u2013', ' to ')
    text = text.replace('\u00b7', ',')
    text = text.replace('\u00b1', 'plus or minus ')
    text = text.replace('\u2264', 'less than or equal to ')
    text = text.replace('\u2265', 'greater than or equal to ')
    text = text.replace('\u00d7', 'times ')
    # Ranges: P10-P90 -> P10 to P90, 10-20 -> 10 to 20
    text = re.sub(r'(\w+)\u2013(\w+)', r'\1 to \2', text)
    text = re.sub(r'(P\d+)-(P\d+)', r'\1 to \2', text)
    text = re.sub(r'(\d+\.?\d*)-(\d+\.?\d*)', r'\1 to \2', text)
    # Standalone dash as separator
    text = re.sub(r' - ', ', ', text)
    # T&M -> T and M
    text = text.replace('T&M', 'T and M')
    # Money: £12.3M -> 12.3 million pounds, £450k -> 450 thousand pounds
    text = re.sub(r'£([\d,]+\.?\d*)M', r'\1 million pounds', text)
    text = re.sub(r'£([\d,]+\.?\d*)k', r'\1 thousand pounds', text)
    text = re.sub(r'£([\d,]+\.?\d*)', r'\1 pounds', text)
    # Percentages: +3.1% -> plus 3.1 percent, -12.4% -> minus 12.4 percent
    text = re.sub(r'\+(\d+\.?\d*)%', r'plus \1 percent', text)
    text = re.sub(r'-(\d+\.?\d*)%', r'minus \1 percent', text)
    text = re.sub(r'(\d+\.?\d*)%', r'\1 percent', text)
    # Signed numbers without %: +3.1 -> plus 3.1, already handled by above
    text = re.sub(r'\+(\d+\.?\d*)pp', r'plus \1 percentage points', text)
    # Remove commas from large numbers for cleaner speech (1,234 -> 1234)
    text = re.sub(r'(\d),(\d{3})', r'\1\2', text)
    # IDs like SUP007, P002 — add spaces so they're spelled out
    text = re.sub(r'(SUP)(\d+)', r'Supplier \2', text)
    text = re.sub(r'\bP(\d{3})\b', r'Programme \1', text)
    return text


def _render_voice_button(bullets: list[str], persona: str):
    """Auto-generate and autoplay voice briefing, with replay button."""
    cache_key = f"voice_cache_{persona.replace(' ', '_')}"
    btn_key = f"voice_{persona.replace(' ', '_')}"

    # Auto-generate on first load for this persona (cached in session_state)
    if cache_key not in st.session_state and _get_elevenlabs_key():
        plain_text = f"{persona} briefing. " + " ".join(
            _strip_markdown(b) for b in bullets
        )
        with st.spinner("Generating voice briefing\u2026"):
            audio = _generate_voice(plain_text)
        if audio:
            st.session_state[cache_key] = audio

    # Autoplay if we just generated it
    if cache_key in st.session_state:
        st.audio(st.session_state[cache_key], format="audio/mp3", autoplay=True)

    # Replay / regenerate button
    if st.button(f"\U0001f504 Regenerate voice", key=btn_key, type="secondary"):
        plain_text = f"{persona} briefing. " + " ".join(
            _strip_markdown(b) for b in bullets
        )
        with st.spinner("Regenerating voice\u2026"):
            audio = _generate_voice(plain_text)
        if audio:
            st.session_state[cache_key] = audio
            st.rerun()

    if not _get_elevenlabs_key():
        st.info("Add ELEVENLABS_API_KEY to your Streamlit secrets to enable voice briefings.")


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------
def _signed_pct(val: float) -> str:
    """Format a float as a signed percentage like a trading terminal."""
    return f"{val:+.1f}%"


def _colour_pct(val: float) -> str:
    """Return CSS colour for a percentage value: red if negative, green if positive."""
    if val < 0:
        return f"color: {RR_RED}; font-weight: bold"
    elif val > 0:
        return f"color: {RR_GREEN}; font-weight: bold"
    return ""


def _colour_pct_inverse(val: float) -> str:
    """Inverse: red if positive (overspend), green if negative (underspend)."""
    if val > 0:
        return f"color: {RR_RED}; font-weight: bold"
    elif val < 0:
        return f"color: {RR_GREEN}; font-weight: bold"
    return ""


def _fmt_gbp(val: float) -> str:
    if abs(val) >= 1e6:
        return f"\u00a3{val/1e6:,.1f}M"
    return f"\u00a3{val/1e3:,.0f}k"


def _pct_bar_color(val: float) -> str:
    """Return bar colour based on variance sign."""
    return RR_RED if val > 0 else RR_GREEN


# ---------------------------------------------------------------------------
# Data-driven briefing generator
# ---------------------------------------------------------------------------
def _programme_director_briefing(latest: pd.DataFrame, progs: pd.DataFrame) -> list[str]:
    total_forecast = latest["Forecast_Spend"].sum()
    total_actual = latest["Actual_Spend"].sum()
    portfolio_var_pct = (total_actual - total_forecast) / total_forecast * 100
    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100

    worst = progs.sort_values("fail_rate", ascending=False).iloc[0]
    best = progs.sort_values("fail_rate", ascending=True).iloc[0]

    bullets = [
        f"Portfolio variance is **{_signed_pct(portfolio_var_pct)}** "
        f"({'overspend' if portfolio_var_pct > 0 else 'underspend'}) "
        f"against forecast \u2014 {_fmt_gbp(total_actual)} actual vs {_fmt_gbp(total_forecast)} forecast.",
        f"**{fail_rate:.1f}%** of forecast rows breach the CFO confidence tolerance.",
        f"Worst programme: **{worst['Programme_ID']}** with **{worst['fail_rate']*100:.1f}%** failure rate "
        f"and {_fmt_gbp(worst['total_abs_error'])} absolute error.",
        f"Most reliable: **{best['Programme_ID']}** at **{best['fail_rate']*100:.1f}%** failure rate.",
    ]
    queue = build_intervention_queue(latest, top_n=1)
    if not queue.empty:
        top = queue.iloc[0]
        bullets.append(
            f"Top intervention: *{top['action']}* on **{top['target']}** "
            f"\u2014 est. recovery {_fmt_gbp(top['recovery_gbp'])}."
        )
    return bullets


def _cfo_briefing(latest: pd.DataFrame, portfolio_m: pd.DataFrame) -> list[str]:
    total_forecast = latest["Forecast_Spend"].sum()
    total_actual = latest["Actual_Spend"].sum()
    envelope = portfolio_m["envelope"].sum()
    headroom = envelope - total_actual
    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100
    flexible = portfolio_m["flexible"].sum()
    flex_used = max(total_actual - portfolio_m["ringfenced"].sum(), 0)
    flex_remaining = flexible - flex_used

    bullets = [
        f"Portfolio actual spend is {_fmt_gbp(total_actual)} against "
        f"{_fmt_gbp(envelope)} envelope \u2014 headroom of **{_fmt_gbp(headroom)}**.",
        f"Flexible capital remaining: **{_fmt_gbp(flex_remaining)}** "
        f"({flex_remaining/flexible*100:.0f}% of flexible envelope).",
        f"Forecast failure rate: **{fail_rate:.1f}%** \u2014 "
        f"{'above' if fail_rate > 20 else 'within'} acceptable tolerance.",
        f"Portfolio variance: **{_signed_pct((total_actual - total_forecast)/total_forecast*100)}** vs forecast.",
    ]
    progs = programme_view(latest)
    over = progs[progs["total_actual"] > progs["total_forecast"]].sort_values(
        "total_abs_error", ascending=False)
    if not over.empty:
        top_over = over.iloc[0]
        bullets.append(
            f"Highest overspend risk: **{top_over['Programme_ID']}** at "
            f"**{_signed_pct((top_over['total_actual']-top_over['total_forecast'])/top_over['total_forecast']*100)}**."
        )
    return bullets


def _commercial_briefing(latest: pd.DataFrame) -> list[str]:
    league = supplier_league(latest).head(5)
    top_sup = league.iloc[0]
    top_sup_var = (top_sup["total_actual"] - top_sup["total_forecast"]) / top_sup["total_forecast"] * 100

    queue = build_intervention_queue(latest, top_n=10)
    commercial_q = queue[queue["lever"].isin(["Commercial", "Supplier"])] if not queue.empty else pd.DataFrame()

    n_chronic = latest[latest["Supplier_Profile"] == "Chronic Fade"]["Supplier_ID"].nunique()
    n_tm = latest[latest["Contract_Type"] == "T&M"]["Supplier_ID"].nunique()

    bullets = [
        f"Top fade contributor: **{top_sup['Supplier_ID']}** "
        f"({top_sup['Supplier_Profile']}, {top_sup['Contract_Type']}) \u2014 "
        f"**{_signed_pct(top_sup_var)}** variance, {_fmt_gbp(top_sup['total_abs_error'])} |error|.",
        f"**{n_chronic}** suppliers classified as Chronic Fade; **{n_tm}** on T&M contracts.",
        f"**{len(commercial_q)}** commercial/supplier interventions queued "
        f"with est. recovery of **{_fmt_gbp(commercial_q['recovery_gbp'].sum())}**." if not commercial_q.empty
        else "No commercial/supplier interventions currently triggered.",
    ]
    if not commercial_q.empty:
        top_action = commercial_q.iloc[0]
        bullets.append(
            f"Priority action: *{top_action['action']}* targeting **{top_action['target']}**."
        )
    # Worst contract type
    ct = latest.groupby("Contract_Type").agg(
        abs_error=("Absolute_Error", "sum"),
        forecast=("Forecast_Spend", "sum"),
    ).reset_index()
    ct["fade_pct"] = ct["abs_error"] / ct["forecast"] * 100
    worst_ct = ct.sort_values("fade_pct", ascending=False).iloc[0]
    bullets.append(
        f"Worst contract type by fade: **{worst_ct['Contract_Type']}** at "
        f"**{worst_ct['fade_pct']:.1f}%** forecast fade."
    )
    return bullets


def _controls_briefing(latest: pd.DataFrame, fact: pd.DataFrame) -> list[str]:
    avg_stability = latest["Forecast_Stability_Score"].mean()
    max_revisions = latest["Revision_Number"].max()
    avg_revisions = latest["Revision_Number"].mean()

    low_stab = latest.groupby("Supplier_ID")["Forecast_Stability_Score"].mean()
    worst_stab_id = low_stab.idxmin()
    worst_stab_val = low_stab.min()

    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100

    # Late revision volatility
    late_revisions = fact[fact["Revision_Number"] >= 3]
    if not late_revisions.empty:
        late_change = late_revisions["Forecast_Change"].abs().mean()
    else:
        late_change = 0

    bullets = [
        f"Average forecast stability score: **{avg_stability:.2f}** "
        f"(1.0 = perfect). Portfolio failure rate: **{fail_rate:.1f}%**.",
        f"Mean revisions per line: **{avg_revisions:.1f}** (max {max_revisions}). "
        f"Late-stage (rev 3+) mean |change|: **{_fmt_gbp(late_change)}**.",
        f"Lowest stability supplier: **{worst_stab_id}** at **{worst_stab_val:.2f}** \u2014 "
        f"investigate data submission quality.",
    ]

    # Programmes with high scope churn
    prog_churn = latest.groupby("Programme_ID")["Programme_Scope_Churn_Index"].mean()
    high_churn = prog_churn[prog_churn > prog_churn.median() * 1.3]
    if not high_churn.empty:
        bullets.append(
            f"**{len(high_churn)}** programme(s) with above-median scope churn: "
            f"**{', '.join(high_churn.index.tolist())}** \u2014 root cause: change control gaps."
        )

    # Optimistic suppliers with few revisions
    opt_low_rev = latest[(latest["Supplier_Profile"] == "Optimistic") & (latest["Revision_Number"] <= 2)]
    if not opt_low_rev.empty:
        n_opt = opt_low_rev["Supplier_ID"].nunique()
        bullets.append(
            f"**{n_opt}** Optimistic-profile supplier(s) submitting \u22642 revisions \u2014 "
            f"increase forecast cadence to catch drift earlier."
        )
    return bullets


# ---------------------------------------------------------------------------
# 1. Programme Director view
# ---------------------------------------------------------------------------
def render_programme_director(latest: pd.DataFrame, fact: pd.DataFrame,
                              portfolio_m: pd.DataFrame):
    st.markdown("### Programme Director")
    st.caption("*What number do I commit to the CFO, and how confident am I?*")
    st.divider()

    progs = programme_view(latest)

    # Briefing
    bullets = _programme_director_briefing(latest, progs)
    for b in bullets:
        st.markdown(f"- {b}")
    _render_voice_button(bullets, "Programme Director")
    st.divider()

    # KPI strip
    total_forecast = latest["Forecast_Spend"].sum()
    total_actual = latest["Actual_Spend"].sum()
    abs_error = latest["Absolute_Error"].sum()
    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100
    var_pct = (total_actual - total_forecast) / total_forecast * 100

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Forecast Spend", _fmt_gbp(total_forecast))
    k2.metric("Actual Spend", _fmt_gbp(total_actual),
              delta=f"{var_pct:+.1f}% vs forecast",
              delta_color="inverse")
    k3.metric("Forecast Fade (|Error|)", _fmt_gbp(abs_error))
    k4.metric("Failure Rate", f"{fail_rate:.1f}%",
              delta="Above tolerance" if fail_rate > 20 else "Within tolerance",
              delta_color="inverse" if fail_rate > 20 else "normal")

    st.divider()

    # 2026 portfolio forecast band — the hero chart
    st.markdown("### 2026 portfolio forecast \u2014 P10 / P50 / P90 confidence band")
    fc = build_forecast(latest, horizon_months=12)
    portfolio_fc = roll_up(fc.portfolio, freq="M")

    fig_fc = go.Figure()
    # P90/P10 band
    fig_fc.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p90"],
        mode="lines", line=dict(width=0),
        name="P90", showlegend=False, hoverinfo="skip",
    ))
    fig_fc.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p10"],
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(30, 39, 97, 0.15)",
        name="P10\u2013P90 band",
    ))
    # P50 line
    fig_fc.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p50"],
        mode="lines+markers", line=dict(color=RR_NAVY, width=3),
        name="P50 (central)",
    ))
    # 2025 actuals overlay
    actual_rollup = aggregate_by(latest, by="M")
    fig_fc.add_trace(go.Scatter(
        x=actual_rollup["bucket"], y=actual_rollup["actual"],
        mode="lines+markers", line=dict(color=RR_GOLD, width=2, dash="dash"),
        name="2025 Actual",
    ))
    fig_fc.update_layout(
        height=450, margin=dict(l=10, r=10, t=20, b=10),
        yaxis_title="\u00a3 spend", xaxis_title=None,
        hovermode="x unified", legend=dict(orientation="h", y=-0.15),
        plot_bgcolor="white",
    )
    fig_fc.update_yaxes(tickprefix="\u00a3", tickformat=",.0f", gridcolor="#EEE")
    fig_fc.update_xaxes(gridcolor="#EEE")
    st.plotly_chart(fig_fc, use_container_width=True)

    # Summary stats under the chart
    p50_2026 = portfolio_fc["p50"].sum()
    p10_2026 = portfolio_fc["p10"].sum()
    p90_2026 = portfolio_fc["p90"].sum()
    c1, c2, c3 = st.columns(3)
    c1.metric("2026 P50 (central)", f"\u00a3{p50_2026/1e6:,.1f}M")
    c2.metric("2026 P10 (best case)", f"\u00a3{p10_2026/1e6:,.1f}M")
    c3.metric("2026 P90 (worst case)", f"\u00a3{p90_2026/1e6:,.1f}M",
              delta=f"\u00b1\u00a3{(p90_2026-p10_2026)/2/1e6:,.1f}M uncertainty")

    st.divider()

    # Programme breakdown table with conditional formatting
    st.markdown("### Programme breakdown")
    progs = progs.copy()
    progs["variance_pct"] = ((progs["total_actual"] - progs["total_forecast"])
                              / progs["total_forecast"].replace(0, 1) * 100)
    progs["fail_rate_pct"] = progs["fail_rate"] * 100

    display = progs[["Programme_ID", "Programme_Phase", "Delivery_Risk",
                      "total_forecast", "total_actual", "total_abs_error",
                      "variance_pct", "fail_rate_pct"]].copy()
    display.columns = ["Programme", "Phase", "Risk", "Forecast (£)",
                        "Actual (£)", "|Error| (£)", "Variance %", "Fail %"]

    # Style the dataframe
    styled = (display.style
              .format({
                  "Forecast (£)": lambda x: _fmt_gbp(x),
                  "Actual (£)": lambda x: _fmt_gbp(x),
                  "|Error| (£)": lambda x: _fmt_gbp(x),
                  "Variance %": lambda x: _signed_pct(x),
                  "Fail %": lambda x: f"{x:.1f}%",
              })
              .map(_colour_pct_inverse, subset=["Variance %"])
              .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 20
                   else "", subset=["Fail %"]))
    st.dataframe(styled, hide_index=True, use_container_width=True)
    st.download_button(
        "\u2b07 Download programme breakdown (CSV)",
        data=display.to_csv(index=False),
        file_name="programme_breakdown.csv",
        mime="text/csv",
        key="dl_prog_breakdown",
    )

    # Forecast confidence chart by programme
    st.markdown("### 2026 forecast confidence by programme")

    fig = go.Figure()
    prog_ids = fc.by_programme["Programme_ID"].unique()
    colors = [RR_NAVY, RR_GOLD, "#4B9CD3", "#8B4789", RR_RED, RR_GREEN, "#FF6B35", "#A0522D"]
    for i, pid in enumerate(prog_ids):
        pdf = fc.by_programme[fc.by_programme["Programme_ID"] == pid]
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=pdf["period_ts"], y=pdf["p50"],
            mode="lines+markers", name=pid,
            line=dict(color=color, width=2),
        ))
    fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10),
                      hovermode="x unified", legend=dict(orientation="h", y=-0.2),
                      plot_bgcolor="white", yaxis_title="£ spend (P50)")
    fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    fig.update_xaxes(gridcolor="#EEE")
    st.plotly_chart(fig, use_container_width=True)

    # Top interventions
    st.markdown("### Top 5 interventions")
    queue = build_intervention_queue(latest, top_n=5)
    if not queue.empty:
        q_display = queue[["rank", "target", "lever", "action", "recovery_gbp"]].copy()
        q_display["recovery_gbp"] = q_display["recovery_gbp"].apply(_fmt_gbp)
        q_display.columns = ["#", "Target", "Lever", "Action", "Recovery"]
        st.dataframe(q_display, hide_index=True, use_container_width=True)


# ---------------------------------------------------------------------------
# 2. CFO view
# ---------------------------------------------------------------------------
def render_cfo(latest: pd.DataFrame, fact: pd.DataFrame,
               portfolio_m: pd.DataFrame):
    st.markdown("### CFO")
    st.caption("*Can I trust this programme's number, and how much flexible capital can I release?*")
    st.divider()

    # Briefing
    bullets = _cfo_briefing(latest, portfolio_m)
    for b in bullets:
        st.markdown(f"- {b}")
    _render_voice_button(bullets, "CFO")
    st.divider()

    # KPI strip
    total_forecast = latest["Forecast_Spend"].sum()
    total_actual = latest["Actual_Spend"].sum()
    envelope = portfolio_m["envelope"].sum()
    headroom = envelope - total_actual
    flexible = portfolio_m["flexible"].sum()
    ringfenced_total = portfolio_m["ringfenced"].sum()
    flex_used = max(total_actual - ringfenced_total, 0)
    flex_remaining = flexible - flex_used
    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Envelope", _fmt_gbp(envelope))
    k2.metric("Actual Spend", _fmt_gbp(total_actual))
    k3.metric("Headroom", _fmt_gbp(headroom))
    k4.metric("Flexible Capital Free", _fmt_gbp(flex_remaining))
    k5.metric("Failure Rate", f"{fail_rate:.1f}%")

    st.divider()

    # Envelope vs Forecast vs Actual
    st.markdown("### Envelope utilisation")
    pm = portfolio_m.copy()
    pm["period_ts"] = pd.to_datetime(pm["period_ts"])
    pm["bucket"] = pm["period_ts"].dt.to_period("M").dt.to_timestamp()
    roll = pm.groupby("bucket").agg(
        forecast=("forecast", "sum"),
        actual=("actual", "sum"),
        envelope=("envelope", "sum"),
        ringfenced=("ringfenced", "sum"),
        flexible=("flexible", "sum"),
    ).reset_index()

    fig = go.Figure()
    fig.add_trace(go.Bar(x=roll["bucket"], y=roll["envelope"],
                         name="Envelope", marker_color=RR_LIGHT_BLUE))
    fig.add_trace(go.Scatter(x=roll["bucket"], y=roll["forecast"],
                             name="Forecast", mode="lines+markers",
                             line=dict(color=RR_NAVY, width=3)))
    fig.add_trace(go.Scatter(x=roll["bucket"], y=roll["actual"],
                             name="Actual", mode="lines+markers",
                             line=dict(color=RR_GOLD, width=3, dash="dash")))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      hovermode="x unified", legend=dict(orientation="h", y=-0.15),
                      plot_bgcolor="white", yaxis_title="£ spend")
    fig.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    fig.update_xaxes(gridcolor="#EEE")
    st.plotly_chart(fig, use_container_width=True)

    # Programme trust table
    st.markdown("### Programme trust assessment")
    progs = programme_view(latest)
    progs["variance_pct"] = ((progs["total_actual"] - progs["total_forecast"])
                              / progs["total_forecast"].replace(0, 1) * 100)
    progs["fail_rate_pct"] = progs["fail_rate"] * 100

    display = progs[["Programme_ID", "Programme_Phase", "Delivery_Risk",
                      "total_forecast", "total_actual", "variance_pct",
                      "fail_rate_pct"]].copy()
    display.columns = ["Programme", "Phase", "Risk", "Forecast (£)",
                        "Actual (£)", "Variance %", "Fail %"]

    styled = (display.style
              .format({
                  "Forecast (£)": lambda x: _fmt_gbp(x),
                  "Actual (£)": lambda x: _fmt_gbp(x),
                  "Variance %": lambda x: _signed_pct(x),
                  "Fail %": lambda x: f"{x:.1f}%",
              })
              .map(_colour_pct_inverse, subset=["Variance %"])
              .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 20
                   else "", subset=["Fail %"]))
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # Gauge charts
    st.markdown("### Envelope utilisation gauges")
    col1, col2 = st.columns(2)
    with col1:
        rf_used = min(ringfenced_total, total_actual)
        rf_pct = rf_used / ringfenced_total * 100 if ringfenced_total else 0
        fig_rf = go.Figure(go.Indicator(
            mode="gauge+number",
            value=rf_pct,
            number={"suffix": "%"},
            title={"text": "Ringfenced utilisation"},
            gauge={"axis": {"range": [0, 110]},
                   "bar": {"color": RR_NAVY},
                   "steps": [
                       {"range": [0, 80], "color": "#E8F0FE"},
                       {"range": [80, 100], "color": RR_LIGHT_BLUE},
                       {"range": [100, 110], "color": "#FFCCCC"},
                   ]}))
        fig_rf.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_rf, use_container_width=True)

    with col2:
        flex_pct = flex_used / flexible * 100 if flexible else 0
        fig_fx = go.Figure(go.Indicator(
            mode="gauge+number",
            value=flex_pct,
            number={"suffix": "%"},
            title={"text": "Flexible utilisation"},
            gauge={"axis": {"range": [0, 110]},
                   "bar": {"color": RR_GOLD},
                   "steps": [
                       {"range": [0, 60], "color": "#FFF3D6"},
                       {"range": [60, 100], "color": "#FFE099"},
                       {"range": [100, 110], "color": "#FFCCCC"},
                   ]}))
        fig_fx.update_layout(height=250, margin=dict(l=10, r=10, t=40, b=10))
        st.plotly_chart(fig_fx, use_container_width=True)

    # 2026 outlook
    st.markdown("### 2026 outlook (P10 / P50 / P90)")
    fc = build_forecast(latest, horizon_months=12)
    portfolio_fc = roll_up(fc.portfolio, freq="Q")

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p90"],
        line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig2.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p10"],
        line=dict(width=0), fill="tonexty",
        fillcolor="rgba(30,39,97,0.15)", name="P10\u2013P90 band"))
    fig2.add_trace(go.Scatter(
        x=portfolio_fc["period_ts"], y=portfolio_fc["p50"],
        mode="lines+markers", line=dict(color=RR_NAVY, width=3),
        name="P50 central"))
    fig2.update_layout(height=380, margin=dict(l=10, r=10, t=10, b=10),
                       hovermode="x unified",
                       legend=dict(orientation="h", y=-0.15),
                       plot_bgcolor="white", yaxis_title="£ spend")
    fig2.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    fig2.update_xaxes(gridcolor="#EEE")
    st.plotly_chart(fig2, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("2026 P50", f"£{portfolio_fc['p50'].sum()/1e6:,.1f}M")
    c2.metric("2026 P10 (upside)", f"£{portfolio_fc['p10'].sum()/1e6:,.1f}M")
    c3.metric("2026 P90 (downside)", f"£{portfolio_fc['p90'].sum()/1e6:,.1f}M")


# ---------------------------------------------------------------------------
# 3. Commercial Manager view
# ---------------------------------------------------------------------------
def render_commercial_manager(latest: pd.DataFrame, fact: pd.DataFrame,
                              portfolio_m: pd.DataFrame):
    st.markdown("### Commercial Manager")
    st.caption("*Which supplier or contract do I intervene on this week?*")
    st.divider()

    # Briefing
    bullets = _commercial_briefing(latest)
    for b in bullets:
        st.markdown(f"- {b}")
    _render_voice_button(bullets, "Commercial Manager")
    st.divider()

    # KPI strip
    league = supplier_league(latest)
    n_suppliers = latest["Supplier_ID"].nunique()
    n_failing = league[league["fail_rate"] > 0.2].shape[0]
    total_error = latest["Absolute_Error"].sum()
    queue = build_intervention_queue(latest, top_n=50)
    commercial_q = queue[queue["lever"].isin(["Commercial", "Supplier"])] if not queue.empty else pd.DataFrame()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Suppliers", n_suppliers)
    k2.metric("Suppliers failing (>20%)", n_failing,
              delta=f"{n_failing/n_suppliers*100:.0f}% of base",
              delta_color="inverse")
    k3.metric("Total |Error|", _fmt_gbp(total_error))
    k4.metric("Commercial actions queued", len(commercial_q))

    st.divider()

    # Supplier league with conditional formatting
    st.markdown("### Supplier league \u2014 ranked by forecast fade")
    league_top = league.head(15).copy()
    league_top["variance_pct"] = ((league_top["total_actual"] - league_top["total_forecast"])
                                   / league_top["total_forecast"].replace(0, 1) * 100)
    league_top["fail_rate_pct"] = league_top["fail_rate"] * 100

    display = league_top[["Supplier_ID", "Supplier_Profile", "Contract_Type",
                           "Region", "Strategic_Flag", "total_forecast",
                           "total_actual", "total_abs_error", "variance_pct",
                           "fail_rate_pct"]].copy()
    display.columns = ["Supplier", "Profile", "Contract", "Region", "Strategic",
                        "Forecast (£)", "Actual (£)", "|Error| (£)",
                        "Variance %", "Fail %"]

    styled = (display.style
              .format({
                  "Forecast (£)": lambda x: _fmt_gbp(x),
                  "Actual (£)": lambda x: _fmt_gbp(x),
                  "|Error| (£)": lambda x: _fmt_gbp(x),
                  "Variance %": lambda x: _signed_pct(x),
                  "Fail %": lambda x: f"{x:.1f}%",
              })
              .map(_colour_pct_inverse, subset=["Variance %"])
              .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 20
                   else "", subset=["Fail %"]))
    st.dataframe(styled, hide_index=True, use_container_width=True, height=450)
    st.download_button(
        "\u2b07 Download supplier league (CSV)",
        data=display.to_csv(index=False),
        file_name="supplier_league.csv",
        mime="text/csv",
        key="dl_supplier_league",
    )

    # Variance by contract type chart
    st.markdown("### Forecast fade by contract type")
    ct = latest.groupby("Contract_Type").agg(
        forecast=("Forecast_Spend", "sum"),
        actual=("Actual_Spend", "sum"),
        abs_error=("Absolute_Error", "sum"),
    ).reset_index()
    ct["variance_pct"] = (ct["actual"] - ct["forecast"]) / ct["forecast"] * 100
    ct["fade_pct"] = ct["abs_error"] / ct["forecast"] * 100

    bar_colors = [RR_RED if v > 0 else RR_GREEN for v in ct["variance_pct"]]
    fig = go.Figure(go.Bar(
        x=ct["Contract_Type"], y=ct["variance_pct"],
        marker_color=bar_colors,
        text=ct["variance_pct"].apply(lambda v: _signed_pct(v)),
        textposition="outside",
    ))
    fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                      plot_bgcolor="white", yaxis_title="Variance %",
                      showlegend=False)
    fig.update_yaxes(ticksuffix="%", gridcolor="#EEE", zeroline=True,
                     zerolinecolor="#333")
    st.plotly_chart(fig, use_container_width=True)

    # Supplier profile breakdown
    st.markdown("### Supplier profile \u2014 error concentration")
    prof = latest.groupby("Supplier_Profile").agg(
        total_error=("Absolute_Error", "sum"),
        total_forecast=("Forecast_Spend", "sum"),
        n=("Supplier_ID", "nunique"),
    ).reset_index()
    prof["fade_pct"] = prof["total_error"] / prof["total_forecast"] * 100

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=prof["Supplier_Profile"], y=prof["total_error"],
        name="|Error|", marker_color=RR_NAVY,
        text=prof["total_error"].apply(lambda x: _fmt_gbp(x)),
        textposition="outside",
    ))
    fig2.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10),
                       plot_bgcolor="white", yaxis_title="Total |Error| (£)",
                       showlegend=False)
    fig2.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    st.plotly_chart(fig2, use_container_width=True)

    # Commercial intervention queue
    st.markdown("### Commercial & supplier intervention queue")
    if not commercial_q.empty:
        cq_display = commercial_q[["rank", "target", "lever", "rule",
                                    "action", "recovery_gbp"]].copy()
        cq_display["recovery_gbp"] = cq_display["recovery_gbp"].apply(_fmt_gbp)
        cq_display.columns = ["#", "Target", "Lever", "Rule", "Action", "Recovery"]
        st.dataframe(cq_display, hide_index=True, use_container_width=True)
    else:
        st.info("No commercial/supplier interventions currently triggered.")


# ---------------------------------------------------------------------------
# 4. Project Controls Lead view
# ---------------------------------------------------------------------------
def render_project_controls(latest: pd.DataFrame, fact: pd.DataFrame,
                            portfolio_m: pd.DataFrame):
    st.markdown("### Project Controls Lead")
    st.caption("*Which behaviours or data-quality issues do I fix to improve forecasting over time?*")
    st.divider()

    # Briefing
    bullets = _controls_briefing(latest, fact)
    for b in bullets:
        st.markdown(f"- {b}")
    _render_voice_button(bullets, "Project Controls Lead")
    st.divider()

    # KPI strip
    avg_stability = latest["Forecast_Stability_Score"].mean()
    avg_revisions = latest["Revision_Number"].mean()
    fail_rate = latest["Forecast_Failed_Flag"].mean() * 100
    n_profiles = latest["Supplier_Profile"].nunique()

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Avg Stability Score", f"{avg_stability:.2f}",
              help="1.0 = perfect forecast accuracy")
    k2.metric("Avg Revisions/Line", f"{avg_revisions:.1f}")
    k3.metric("Failure Rate", f"{fail_rate:.1f}%")
    k4.metric("Supplier Profiles", n_profiles)

    st.divider()

    # Stability by supplier
    st.markdown("### Forecast stability by supplier")
    sup_stab = latest.groupby(["Supplier_ID", "Supplier_Profile"]).agg(
        stability=("Forecast_Stability_Score", "mean"),
        fail_rate=("Forecast_Failed_Flag", "mean"),
        abs_error=("Absolute_Error", "sum"),
        n_revisions=("Revision_Number", "mean"),
    ).reset_index()
    sup_stab["fail_rate_pct"] = sup_stab["fail_rate"] * 100

    display = sup_stab.sort_values("stability").copy()
    display_df = display[["Supplier_ID", "Supplier_Profile", "stability",
                           "fail_rate_pct", "n_revisions", "abs_error"]].copy()
    display_df.columns = ["Supplier", "Profile", "Stability", "Fail %",
                           "Avg Revisions", "|Error| (£)"]

    styled = (display_df.style
              .format({
                  "Stability": "{:.2f}",
                  "Fail %": lambda x: f"{x:.1f}%",
                  "Avg Revisions": "{:.1f}",
                  "|Error| (£)": lambda x: _fmt_gbp(x),
              })
              .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v < 0.5
                   else (f"color: {RR_GOLD}; font-weight: bold" if v < 0.7 else ""),
                   subset=["Stability"])
              .map(lambda v: f"color: {RR_RED}; font-weight: bold" if v > 20
                   else "", subset=["Fail %"]))
    st.dataframe(styled, hide_index=True, use_container_width=True)

    # Fade curve
    st.markdown("### Forecast fade signature")
    st.caption("How error narrows as the spend period approaches \u2014 the classic 'fade' pattern.")
    fc_curve = fade_curve(fact)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=fc_curve["days_bucket"].astype(str),
        y=fc_curve["mean_error_pct"],
        marker_color=RR_NAVY,
        name="Mean |Error|", yaxis="y1",
    ))
    fig.add_trace(go.Scatter(
        x=fc_curve["days_bucket"].astype(str),
        y=fc_curve["mean_stability"],
        mode="lines+markers", line=dict(color=RR_GOLD, width=3),
        name="Stability score", yaxis="y2",
    ))
    fig.update_layout(
        height=400, margin=dict(l=10, r=10, t=10, b=10),
        plot_bgcolor="white",
        yaxis=dict(title="Mean |Error| (£)", tickprefix="£", tickformat=",.0f",
                   gridcolor="#EEE"),
        yaxis2=dict(title="Stability score", overlaying="y", side="right",
                    range=[0, 1]),
        legend=dict(orientation="h", y=-0.15),
        xaxis_title="Days before spend period",
    )
    st.plotly_chart(fig, use_container_width=True)

    # Revision drift
    st.markdown("### Revision-by-revision drift")
    st.caption("Late revisions with large swings indicate structural baseline issues.")
    rev = fade_by_revision(fact)

    bar_colors = [RR_RED if r["mean_abs_change"] > rev["mean_abs_change"].median() * 1.2
                  else RR_NAVY for _, r in rev.iterrows()]
    fig2 = go.Figure(go.Bar(
        x=rev["Revision_Number"], y=rev["mean_abs_change"],
        marker_color=bar_colors,
        text=rev["mean_abs_change"].apply(lambda x: f"£{x/1e3:,.0f}k"),
        textposition="outside",
    ))
    fig2.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                       plot_bgcolor="white",
                       xaxis_title="Revision number",
                       yaxis_title="Mean |forecast change|")
    fig2.update_yaxes(tickprefix="£", tickformat=",.0f", gridcolor="#EEE")
    st.plotly_chart(fig2, use_container_width=True)

    # Scope churn by programme
    st.markdown("### Programme scope churn index")
    prog_churn = latest.groupby("Programme_ID").agg(
        churn=("Programme_Scope_Churn_Index", "mean"),
        change_impact=("Programme_Change_Impact_Index", "mean"),
        fail_rate=("Forecast_Failed_Flag", "mean"),
    ).reset_index()
    prog_churn["fail_rate_pct"] = prog_churn["fail_rate"] * 100
    median_churn = prog_churn["churn"].median()

    bar_colors_churn = [RR_RED if c > median_churn * 1.3 else RR_NAVY
                        for c in prog_churn["churn"]]
    fig3 = go.Figure(go.Bar(
        x=prog_churn["Programme_ID"], y=prog_churn["churn"],
        marker_color=bar_colors_churn,
        text=prog_churn["churn"].apply(lambda x: f"{x:.2f}"),
        textposition="outside",
    ))
    fig3.add_hline(y=median_churn, line_dash="dash", line_color=RR_GOLD,
                   annotation_text=f"Median: {median_churn:.2f}")
    fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10),
                       plot_bgcolor="white",
                       xaxis_title="Programme", yaxis_title="Scope Churn Index")
    fig3.update_yaxes(gridcolor="#EEE")
    st.plotly_chart(fig3, use_container_width=True)

    # Governance intervention queue
    st.markdown("### Governance interventions")
    queue = build_intervention_queue(latest, top_n=50)
    gov_q = queue[queue["lever"] == "Governance"] if not queue.empty else pd.DataFrame()
    if not gov_q.empty:
        gq_display = gov_q[["rank", "target", "rule", "action", "recovery_gbp"]].copy()
        gq_display["recovery_gbp"] = gq_display["recovery_gbp"].apply(_fmt_gbp)
        gq_display.columns = ["#", "Target", "Rule", "Action", "Recovery"]
        st.dataframe(gq_display, hide_index=True, use_container_width=True)
    else:
        st.info("No governance interventions currently triggered.")
