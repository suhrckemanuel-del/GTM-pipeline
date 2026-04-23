"""
humanizer.py — Step 3: Humanizer Drafter (anti-AI agent).

This is intentionally NOT a creative writer. The pattern, lifted from
scripts/humanize_akirolabs_outreach.py, is:

    [Specific Observation]  +  [Akirolabs Proof Point]  +  [Specific Workflow Offer]

Only the Specific Observations and the Before/After narrative come from an LLM
(under a strict structured-output schema). The proof points and offer templates
come from fixed string banks — eliminating all LLM "voice", banned vocab, and
formulaic CTAs by construction.

The output is a guaranteed-shape ProspectCard validated by Pydantic.
"""
from __future__ import annotations

import os
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from app.services.humanizer_rules import humanize_angle_draft

from .state import (
    ANGLE_DESCRIPTIONS,
    ANGLE_KEYS,
    AngleDraft,
    BDRState,
    HumanizerObservations,
    ProspectCard,
)

MODEL = "claude-sonnet-4-6"

# ---------------------------------------------------------------------------
# Fixed string banks — proof points, offers, fillers, subject templates
# Adapted from scripts/humanize_akirolabs_outreach.py
# ---------------------------------------------------------------------------
ANGLE_PROOFS: dict[str, list[str]] = {
    "angle1": [
        "Bertelsmann used Akirolabs across 7 divisions and cut strategy refresh time by up to 90%.",
        "At Bertelsmann, Akirolabs moved category strategy work across 7 divisions from weeks to days.",
        "Bertelsmann used Akirolabs to compress multi-division strategy refreshes into a days-long workflow.",
    ],
    "angle2": [
        "Merck uses Akirolabs as the strategy layer above its existing procurement stack, so the suite stays in place.",
        "Merck and Axpo run Akirolabs on top of the execution stack they already own, with no replacement project attached.",
        "At Merck, Akirolabs handles the strategy work before decisions flow into the downstream procurement tools.",
    ],
    "angle3": [
        "Raiffeisen Bank used Akirolabs to bring neglected categories under formal strategy without adding headcount.",
        "Raiffeisen Bank used Akirolabs to move autopilot categories back under documented strategy and expand coverage.",
        "Raiffeisen Bank used Akirolabs to increase spend under strategy across categories that had been running on inertia.",
    ],
}

EMAIL_OFFERS: dict[str, list[str]] = {
    "angle1": [
        "I can walk through the Bertelsmann workflow and map it to {company}.",
        "I can share the operating model behind Bertelsmann's rollout and where it fits {company}.",
        "I can send the Bertelsmann workflow and show where it would apply at {company}.",
    ],
    "angle2": [
        "I can show the Merck architecture and where it would sit on top of {company}'s stack.",
        "I can walk through the strategy-layer setup Merck uses and map it to {company}.",
        "I can share the stack view Merck uses and where the same layer would fit at {company}.",
    ],
    "angle3": [
        "I can share the spend-under-strategy benchmark we use for {industry}.",
        "I can send the benchmark we use for {industry} and the first coverage gaps teams usually find.",
        "I can share the benchmark view for {industry} and where teams usually start.",
    ],
}

DM_OFFERS: dict[str, list[str]] = {
    "angle1": [
        "I can map that workflow to {company}.",
        "I can show where that fits {company}.",
        "I can send the workflow for {company}.",
    ],
    "angle2": [
        "I can show where that fits {company}'s stack.",
        "I can map that setup to {company}.",
        "I can share where that layer fits at {company}.",
    ],
    "angle3": [
        "I can share the benchmark for {industry}.",
        "I can send the benchmark and first gaps.",
        "I can share where teams usually start.",
    ],
}

EMAIL_FILLERS_P1: dict[str, str] = {
    "angle1": "That usually leaves teams reacting late to market moves.",
    "angle2": "That planning gap usually slows decisions before execution begins.",
    "angle3": "That usually means part of the portfolio is still running on inertia.",
}

EMAIL_FILLERS_P3: dict[str, str] = {
    "angle1": "That is usually where the manual process falls behind first.",
    "angle2": "That planning gap usually sits above the suite, not inside it.",
    "angle3": "That is usually where teams discover how much spend is still uncovered.",
}

EMAIL_FILLERS_P2: dict[str, str] = {
    "angle1": "It gave category teams a faster way to keep strategy current.",
    "angle2": "It gave category teams a dedicated place to do the planning work first.",
    "angle3": "It gave the team a scalable way to widen strategic coverage.",
}

SUBJECT_TEMPLATES: dict[str, list[str]] = {
    "angle1": [
        "Faster category strategy at {company}",
        "{company} category strategy refresh",
        "Cycle time on {company} sourcing strategy",
    ],
    "angle2": [
        "Strategy layer above {company}'s stack",
        "{company} planning gap above the suite",
        "Pre-sourcing strategy at {company}",
    ],
    "angle3": [
        "Spend under strategy at {company}",
        "{company} indirect coverage gap",
        "Tail spend strategy at {company}",
    ],
}


# ---------------------------------------------------------------------------
# Text utilities (lifted from humanize_akirolabs_outreach.py)
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    cleaned = (text or "").replace("\u2014", ", ")  # em dash -> comma
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:?!])", r"\1", cleaned)
    return cleaned.strip()


def _trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:")
    if trimmed and trimmed[-1] not in ".!":
        trimmed += "."
    return trimmed


def _word_count(text: str) -> int:
    return len(text.replace("\n", " ").split())


# ---------------------------------------------------------------------------
# LLM call — produce only the things we cannot template
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """\
You are the Observation Generator for the Humanizer agent.

You are NOT writing emails. You are producing 5 short text snippets that the \
deterministic assembler will glue into emails using fixed templates. Your only \
job is specificity — name the actual category, the actual driver, the actual \
constraint at this company.

Rules:
  - No buzzwords: never use "actually", "additionally", "transformative", \
"leverage" (verb), "showcasing", "landscape", "actively".
  - No questions, no rhetorical openers.
  - Each observation must be ONE sentence, max ~22 words.
  - The observation must reference a real spend category (e.g. "indirect \
services", "logistics", "IT contractors") or a concrete operating constraint.
  - Before/After narrative: 2 short paragraphs. The After paragraph must \
mention what akiroAssist does (synthesises market intelligence, auto-populates \
risk/SWOT frameworks, models scenarios, generates stakeholder summaries) and \
the "up to 90% faster" stat.
  - The After paragraph MUST NOT start with the literal string "With Akirolabs:" \
— the assembler prepends that prefix."""


def _generate_observations(
    company: str,
    industry: str,
    research_summary: str,
    pain_signal: str,
    persona: str,
) -> HumanizerObservations:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return HumanizerObservations(
            angle1_observation=f"{company} runs category strategy on long manual cycles.",
            angle2_observation=f"{company} has execution tooling but no strategy automation above it.",
            angle3_observation=f"{company} has indirect categories without a documented strategy.",
            before_text=f"{company}'s procurement team builds category strategies in slide decks across many weeks.",
            after_text="akiroAssist synthesises market intelligence, auto-populates risk/SWOT frameworks, models scenarios, and produces stakeholder summaries up to 90% faster.",
        )

    llm = ChatAnthropic(model=MODEL, api_key=api_key, max_tokens=900, temperature=0.4)
    structured = llm.with_structured_output(HumanizerObservations)

    user = (
        f"Company: {company}\n"
        f"Industry: {industry or 'unknown'}\n"
        f"Likely persona: {persona}\n"
        f"Specific pain to anchor: {pain_signal}\n\n"
        f"Research summary (from prior agents):\n{research_summary or '(none)'}\n\n"
        "Produce HumanizerObservations: three one-sentence observations (one per angle) "
        "and the two-paragraph Before/After narrative. Be concrete and specific."
    )
    try:
        return structured.invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=user)]
        )
    except Exception:
        return HumanizerObservations(
            angle1_observation=f"{company} runs category strategy on long manual cycles.",
            angle2_observation=f"{company} has execution tooling but no strategy automation above it.",
            angle3_observation=f"{company} has indirect categories without a documented strategy.",
            before_text=f"{company} builds category strategies in slide decks across many weeks.",
            after_text="akiroAssist synthesises market intelligence and produces stakeholder summaries up to 90% faster.",
        )


# ---------------------------------------------------------------------------
# Deterministic assembly
# ---------------------------------------------------------------------------
def _variant_index(company: str, angle_idx: int) -> int:
    """Same idea as the original script — stable per-company variant pick."""
    return (sum(ord(c) for c in company.lower()) + angle_idx) % 3


def _assemble_email(
    angle_key: str, observation: str, company: str, industry: str, variant: int
) -> str:
    p1 = _clean(observation)
    p2 = ANGLE_PROOFS[angle_key][variant]
    p3 = EMAIL_OFFERS[angle_key][variant].format(company=company, industry=industry)

    email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
    wc = _word_count(email)

    if wc < 80:
        p1 = f"{p1} {EMAIL_FILLERS_P1[angle_key]}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        wc = _word_count(email)
    if wc < 80:
        p3 = f"{p3} {EMAIL_FILLERS_P3[angle_key]}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        wc = _word_count(email)
    if wc < 80:
        p2 = f"{p2} {EMAIL_FILLERS_P2[angle_key]}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        wc = _word_count(email)
    if wc < 80:
        p1 = f"{p1} The backlog is usually visible well before the board sees it."
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        wc = _word_count(email)
    if wc > 100:
        overflow = wc - 100
        target = max(18, len(p1.split()) - overflow)
        p1 = _trim_words(p1, target)
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
    return email


def _assemble_dm(
    angle_key: str, observation: str, company: str, industry: str, variant: int
) -> str:
    obs = _trim_words(_clean(observation), 14)
    proof = _trim_words(ANGLE_PROOFS[angle_key][variant], 10)
    offer = _trim_words(
        DM_OFFERS[angle_key][variant].format(company=company, industry=industry), 9
    )
    dm = f"{obs} {proof} {offer}\n\nManuel"
    if _word_count(dm) > 60:
        dm = f"{_trim_words(obs, 12)} {_trim_words(proof, 9)} {_trim_words(offer, 8)}\n\nManuel"
    return dm


def _assemble_subject(angle_key: str, company: str, variant: int) -> str:
    return SUBJECT_TEMPLATES[angle_key][variant].format(company=company)


def _build_angle(
    angle_key: str, observation: str, company: str, industry: str
) -> AngleDraft:
    angle_idx = ANGLE_KEYS.index(angle_key)
    variant = _variant_index(company, angle_idx)
    meta = ANGLE_DESCRIPTIONS[angle_key]
    return AngleDraft(
        angle_key=angle_key,
        name=meta["name"],
        tab_label=meta["tab_label"],
        dm=_assemble_dm(angle_key, observation, company, industry, variant),
        email_subject=_assemble_subject(angle_key, company, variant),
        email_body=_assemble_email(angle_key, observation, company, industry, variant),
    )


def _assemble_before_after(before: str, after: str) -> str:
    before = _clean(before)
    after = _clean(after)
    after = re.sub(r"^\s*With Akirolabs:\s*", "", after, flags=re.I)
    return f"{before}\n\nWith Akirolabs: {after}"


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def run_humanizer(state: BDRState) -> dict:
    if state.get("error"):
        return {}

    enrichment = state.get("enrichment")
    strategy = state.get("strategy")
    if not enrichment or not strategy:
        return {"error": "Humanizer: missing enrichment or strategy."}

    trace = list(state.get("agent_trace", []))
    trace.append("Humanizer: requesting observations under strict schema")

    obs = _generate_observations(
        company=enrichment.company,
        industry=enrichment.industry,
        research_summary=enrichment.research_summary,
        pain_signal=strategy.pain_signal,
        persona=strategy.cpo_hypothesis,
    )

    trace.append("Humanizer: assembling DMs + emails via fixed banks")
    company = enrichment.company
    industry = enrichment.industry or "your industry"
    angles = [
        humanize_angle_draft(_build_angle("angle1", obs.angle1_observation, company, industry)),
        humanize_angle_draft(_build_angle("angle2", obs.angle2_observation, company, industry)),
        humanize_angle_draft(_build_angle("angle3", obs.angle3_observation, company, industry)),
    ]
    card = ProspectCard(
        before_after=_assemble_before_after(obs.before_text, obs.after_text),
        angles=angles,
    )
    trace.append("Humanizer: card assembled + 29-rule filter applied")
    return {"card": card, "agent_trace": trace}
