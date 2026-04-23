"""
gleef_strategist.py — Strategy Agent for Gleef BDR pipeline.

Reads EnrichmentResult and picks ONE of three Gleef angles via structured output.
Angle drives which persona to target and which sequence template to use.
"""
from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .state import BDRState, EnrichmentResult, StrategyDecision

MODEL = "claude-sonnet-4-6"

GLEEF_ANGLE_KEYS = ("angle1", "angle2", "angle3")

GLEEF_ANGLE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "angle1": {
        "name": "Figma-Native Workflow",
        "tab_label": "Figma-Native",
        "description": (
            "Figma-Native Workflow: localization review happens outside Figma, "
            "forcing designers into a second tool and stripping layout context from translations."
        ),
    },
    "angle2": {
        "name": "Developer Experience",
        "tab_label": "Dev Experience",
        "description": (
            "Developer Experience: i18n key chaos, no CI/CD integration, "
            "localization lives outside the git workflow and creates sprint debt."
        ),
    },
    "angle3": {
        "name": "Brand Voice at Scale",
        "tab_label": "Brand Voice",
        "description": (
            "Brand Voice at Scale: translated UI loses brand tone because generic AI "
            "translates segments in isolation without knowing product context or writing rules."
        ),
    },
}

GLEEF_PERSONA_MAP = {
    "angle1": "VP Product / Head of Product",
    "angle2": "VP Engineering / Head of Engineering",
    "angle3": "Head of Design / UX Lead",
}

SYSTEM_PROMPT = """\
You are the Strategy Agent in a B2B sales workflow for Gleef.

Gleef is an AI-powered UI localization platform — Figma plugin + CLI — that moves \
translation review into the design workflow itself. Reference customer: Alan (970K \
members, French health insurance). 200+ companies. Backed by Antler.

Pick exactly ONE angle for this prospect. Be decisive.

Three angles:
  - angle1 (Figma-Native): Target VP Product. Pain: design-to-dev localization adds \
tool switches and layout-blind reviews. Gleef puts translation inside Figma so designers \
validate before code ships.
  - angle2 (Developer Experience): Target VP Engineering. Pain: i18n key chaos (names \
like Frame15034.forgot-password), no CI/CD integration, localization outside the git \
workflow. Gleef CLI fixes this.
  - angle3 (Brand Voice): Target Head of Design / UX Lead. Pain: translated UI loses \
brand tone because generic AI translates isolated segments. Gleef's memory learns brand \
voice and applies it across all languages.

Heuristics:
  - Strong product org + multi-market + fast shipping cadence -> angle1
  - Engineering-heavy culture + dev tools / API company + CI/CD signals -> angle2
  - Strong brand / consumer-grade UX / premium product + UX writing culture -> angle3
  - Default if unclear: angle1 (VP Product has broadest authority over localization)

Also fill: cpo_hypothesis (the target persona title), pain_signal (one specific sentence \
about their localization friction today), rationale (2-3 sentences grounded in enrichment)."""


def _format_enrichment(e: EnrichmentResult) -> str:
    parts: list[str] = []
    if e.icp:
        parts.append(f"ICP Tier: {e.icp.tier_label}\n  Why: {e.icp.rationale}")
    if e.contacts:
        parts.append(
            "Contacts (Hunter.io):\n"
            + "\n".join(
                f"  - {c.name or '(unknown)'} — {c.position or 'unknown'}"
                for c in e.contacts[:5]
            )
        )
    if e.research_summary:
        parts.append(f"Research summary:\n{e.research_summary}")
    if e.live_signals:
        parts.append(
            "Live signals:\n"
            + "\n".join(f"  - {s.title}" for s in e.live_signals[:3])
        )
    return "\n\n".join(parts) or "(no enrichment data)"


def _format_angle_menu() -> str:
    return "\n".join(
        f"- {key} ({GLEEF_ANGLE_DESCRIPTIONS[key]['name']}): {GLEEF_ANGLE_DESCRIPTIONS[key]['description']}"
        for key in GLEEF_ANGLE_KEYS
    )


def run_gleef_strategist(state: BDRState) -> dict:
    """LangGraph node — pick the optimal Gleef angle."""
    if state.get("error"):
        return {}
    enrichment = state.get("enrichment")
    if not enrichment:
        return {"error": "Gleef Strategist: no enrichment data."}

    trace = list(state.get("agent_trace", []))
    trace.append("Strategist: scoring 3 Gleef angles against enrichment data")

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set.", "agent_trace": trace}

    llm = ChatAnthropic(model=MODEL, api_key=api_key, max_tokens=800, temperature=0.3)
    structured = llm.with_structured_output(StrategyDecision)

    user = (
        f"Company: {enrichment.company}\n"
        f"Industry: {enrichment.industry or 'unknown'}\n\n"
        f"Enrichment data:\n{_format_enrichment(enrichment)}\n\n"
        f"Available angles:\n{_format_angle_menu()}\n\n"
        "Pick the single best-fit angle and fill in the StrategyDecision schema. "
        "Set cpo_hypothesis to the exact persona title for this angle."
    )

    try:
        decision: StrategyDecision = structured.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user)]
        )
    except Exception as exc:
        return {"error": f"Gleef Strategist call failed: {exc}", "agent_trace": trace}

    if decision.recommended_angle not in GLEEF_ANGLE_KEYS:
        decision.recommended_angle = "angle1"
        decision.angle_name = GLEEF_ANGLE_DESCRIPTIONS["angle1"]["name"]

    if not decision.cpo_hypothesis or decision.cpo_hypothesis.strip() == "CPO":
        decision.cpo_hypothesis = GLEEF_PERSONA_MAP[decision.recommended_angle]

    trace.append(
        f"Strategist: chose {decision.recommended_angle} ({decision.angle_name}) "
        f"→ target {decision.cpo_hypothesis}"
    )
    return {"strategy": decision, "agent_trace": trace}
