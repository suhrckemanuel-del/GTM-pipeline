"""
strategist.py — Step 2: Strategy Agent.

Reads the EnrichmentResult and picks ONE of three Akirolabs angles via
Pydantic structured output. No regex parsing — guaranteed JSON contract.
"""
from __future__ import annotations

import os

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .state import (
    ANGLE_DESCRIPTIONS,
    ANGLE_KEYS,
    BDRState,
    EnrichmentResult,
    StrategyDecision,
)

MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """\
You are the Strategy Agent in a B2B sales workflow for Akirolabs.

Akirolabs sells category-strategy automation to large-enterprise procurement \
teams (CPO, Head of Strategic Sourcing). Reference customers: Raiffeisen Bank, \
Bertelsmann (7 divisions), Merck, Axpo. Headline proof: up to 90% faster \
category strategy refresh vs. the traditional 6-week PowerPoint cycle.

Pick exactly ONE angle for this prospect. Be decisive — don't hedge.

Three angles:
  - angle1 — Strategy Speed Gap: long manual category strategy cycles, \
leadership pressure to move faster, transformation programmes, M&A.
  - angle2 — Suite Fatigue Wedge: heavy ERP / spend-analytics suite already in \
place but no automation of category strategy narrative or stakeholder decks.
  - angle3 — Unmanaged Spend Trigger: tail-spend or indirect categories growing \
without a documented strategy, analyst bandwidth constraint.

Heuristics:
  - Tier 1 + recent earnings or transformation news -> often angle1.
  - Tier 1 + heavy ERP/SAP mentions -> often angle2.
  - Tier 2 / mid-market or coverage-gap signals -> often angle3.
But override with whatever the actual signals say.

Return your decision via the StrategyDecision schema. Be specific and grounded \
in the enrichment data — no generic procurement platitudes."""


def _format_enrichment(e: EnrichmentResult) -> str:
    parts: list[str] = []
    if e.icp:
        parts.append(f"ICP Tier: {e.icp.tier_label}\n  Why: {e.icp.rationale}")
    if e.contacts:
        parts.append(
            "Contacts on file (Hunter.io):\n"
            + "\n".join(
                f"  - {c.name or '(unknown)'} - {c.position or 'unknown'}"
                for c in e.contacts[:5]
            )
        )
    if e.research_summary:
        parts.append(f"Research summary:\n{e.research_summary}")
    if e.live_signals:
        parts.append(
            "Top live signals:\n"
            + "\n".join(f"  - {s.title}" for s in e.live_signals[:3])
        )
    return "\n\n".join(parts) or "(no enrichment data)"


def _format_angle_menu() -> str:
    return "\n".join(
        f"- {key} ({ANGLE_DESCRIPTIONS[key]['name']}): {ANGLE_DESCRIPTIONS[key]['description']}"
        for key in ANGLE_KEYS
    )


def run_strategist(state: BDRState) -> dict:
    """LangGraph node — pick the optimal angle."""
    if state.get("error"):
        return {}
    enrichment = state.get("enrichment")
    if not enrichment:
        return {"error": "Strategist: no enrichment data."}

    trace = list(state.get("agent_trace", []))
    trace.append("Strategist: scoring 3 angles against enrichment data")

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
        "Pick the single best-fit angle and fill in the StrategyDecision schema."
    )

    try:
        decision: StrategyDecision = structured.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user)]
        )
    except Exception as exc:
        return {"error": f"Strategist call failed: {exc}", "agent_trace": trace}

    if decision.recommended_angle not in ANGLE_KEYS:
        decision.recommended_angle = "angle1"
        decision.angle_name = ANGLE_DESCRIPTIONS["angle1"]["name"]

    trace.append(f"Strategist: chose {decision.recommended_angle} ({decision.angle_name})")
    return {"strategy": decision, "agent_trace": trace}
