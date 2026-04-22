"""
LLM narrative layer — turns structured forecast data into CFO-ready prose.

Two entry points:
    - executive_narrative(context) -> 3-paragraph board briefing
    - ask_the_forecast(question, context) -> free-text Q&A

Uses Anthropic Claude by default, with OpenAI fallback. Both are optional —
if neither key is configured, we return a deterministic template so the
demo never breaks.
"""

from __future__ import annotations

import os
import json
from textwrap import dedent
from typing import Any

import streamlit as st


def _get_anthropic_key() -> str | None:
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")


def _get_openai_key() -> str | None:
    try:
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return os.environ.get("OPENAI_API_KEY")


SYSTEM_PROMPT = dedent("""
    You are a CFO briefing assistant for Rolls-Royce supply-chain spend.
    You receive structured JSON about a supply-chain spend forecast and produce
    concise, board-ready prose.

    Rules:
    - Be specific. Name suppliers, programmes, contract types, and £ numbers.
    - Do not invent data. If the input does not contain the answer, say so.
    - Write for a CFO audience: direct, precise, one paragraph per question.
    - Highlight uncertainty explicitly (P10/P90 bands if present).
    - When prescribing action, link it to a specific supplier/programme and
      a £ recovery estimate if available in the input.
""").strip()


def executive_narrative(context: dict[str, Any]) -> str:
    """Three-paragraph CFO briefing: what, why, what-to-do."""
    prompt = dedent(f"""
        Produce a 3-paragraph executive briefing from this data:

        ```json
        {json.dumps(context, default=str, indent=2)[:6000]}
        ```

        Paragraph 1 — Headline number with confidence band.
        Paragraph 2 — The top three drivers of variance (name suppliers/programmes).
        Paragraph 3 — The top three actions to take next week with £ recovery.
    """).strip()
    return _call_llm(prompt)


PERSONA_PROMPTS = {
    "Programme Director": dedent("""
        You are briefing a **Programme Director** who needs to decide:
        "What number do I commit to the CFO, and how confident am I?"

        From the data below, produce a concise briefing (3–5 bullets):
        - The headline number they should commit (P50) and the confidence range (P10–P90)
        - Which programmes are most/least reliable and why
        - Where forecast failure rates are highest and what that means for their commitment
        - One concrete action they should take before the next CFO review

        Be direct, specific, and name programme IDs and £ figures.
    """).strip(),

    "CFO": dedent("""
        You are briefing a **CFO** who needs to decide:
        "Can I trust this programme's number, and how much flexible capital can I release?"

        From the data below, produce a concise briefing (3–5 bullets):
        - Whether the portfolio forecast is trustworthy and why/why not
        - How much flexible capital is genuinely available for reallocation
        - Which programmes carry the most risk to the committed number
        - The single biggest driver of forecast failure and the £ at stake

        Be direct, specific, and quantify everything in £ and percentages.
    """).strip(),

    "Commercial Manager": dedent("""
        You are briefing a **Commercial Manager** who needs to decide:
        "Which supplier or contract do I intervene on this week?"

        From the data below, produce a concise briefing (3–5 bullets):
        - The top 3 suppliers causing forecast fade, with their profile and contract type
        - Which contract type (T&M, Fixed Price, etc.) is underperforming and by how much
        - The highest-recovery commercial intervention available right now
        - Any supplier showing both poor OTIF and quality incidents

        Be direct, name supplier IDs, contract types, and £ recovery figures.
    """).strip(),

    "Project Controls Lead": dedent("""
        You are briefing a **Project Controls Lead** who needs to decide:
        "Which behaviours or data-quality issues do I fix to improve forecasting over time?"

        From the data below, produce a concise briefing (3–5 bullets):
        - The current average forecast stability score and what it implies
        - Which suppliers have the worst forecast discipline (low stability, few revisions)
        - Which programmes have excessive scope churn driving forecast instability
        - One process change that would most improve forecast accuracy portfolio-wide

        Be specific — name supplier IDs, programme IDs, and quantify the impact.
    """).strip(),
}


def persona_briefing(persona: str, context: dict[str, Any]) -> str:
    """Generate a persona-specific briefing using the LLM."""
    persona_prompt = PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["CFO"])
    prompt = dedent(f"""
        {persona_prompt}

        ```json
        {json.dumps(context, default=str, indent=2)[:6000]}
        ```
    """).strip()
    return _call_llm(prompt)


def ask_the_forecast(question: str, context: dict[str, Any]) -> str:
    """Free-text Q&A. Used by the 'Ask the Forecast' widget."""
    prompt = dedent(f"""
        A Programme Director has asked:

            "{question}"

        Use ONLY the data below to answer. Cite specific supplier IDs,
        programme IDs, contract types, and £ figures. Keep the answer under
        180 words.

        ```json
        {json.dumps(context, default=str, indent=2)[:6000]}
        ```
    """).strip()
    return _call_llm(prompt)


def _call_llm(prompt: str) -> str:
    """Try Anthropic first, then OpenAI, then a deterministic fallback."""
    anth_key = _get_anthropic_key()
    if anth_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=anth_key)
            msg = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=700,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()
        except Exception as e:
            return _fallback(prompt, f"Anthropic error: {e}")

    oa_key = _get_openai_key()
    if oa_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=oa_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=700,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return _fallback(prompt, f"OpenAI error: {e}")

    return _fallback(prompt, "No LLM API key configured — using template")


def _fallback(prompt: str, reason: str) -> str:
    return (
        f"**[Fallback narrative — {reason}]**\n\n"
        "The portfolio forecast for the selected horizon shows a central estimate "
        "with confidence bands. The largest drivers of variance are concentrated in "
        "suppliers flagged as Chronic Fade and Optimistic profiles, particularly those "
        "on T&M contracts. Programme-level scope churn on P002 and P003 is a secondary "
        "driver.\n\n"
        "Recommended top actions: (1) migrate SUP007 from T&M to Fixed Price; "
        "(2) convene a Change Control Board for high-scope-churn programmes; "
        "(3) reallocate unused flexible envelope from under-running programmes.\n\n"
        "_Configure ANTHROPIC_API_KEY or OPENAI_API_KEY in .streamlit/secrets.toml "
        "to enable live LLM narratives._"
    )
