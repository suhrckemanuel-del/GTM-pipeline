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

from app.services.humanizer_rules import humanize_angle_draft, humanize_sequence

from .state import (
    ANGLE_DESCRIPTIONS,
    ANGLE_KEYS,
    AngleDraft,
    BDRState,
    HumanizerObservations,
    OutreachSequence,
    ProspectCard,
    SequenceTouch,
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

# T2 follow-up bodies — Day 3, 40-60w, angle-specific
FOLLOW_UP_BODIES: dict[str, list[str]] = {
    "angle1": [
        "Sent a note on {company}'s strategy cycle last week. If that landed at a bad time, a 15-minute window when the pace picks up would be enough.",
        "Following up on the category strategy refresh gap at {company}. I can send the Bertelsmann workflow one-pager first — no call needed.",
        "Quick follow-up on the cycle time issue at {company}. Happy to share how teams similar in scale solved it without a platform replacement.",
    ],
    "angle2": [
        "Quick follow-up on the planning layer above {company}'s stack. One slide maps where Akirolabs sits — happy to send it.",
        "Following up on the pre-sourcing gap at {company}. Merck's stack view takes two minutes to explain — I can drop it in an email.",
        "Last week's note was about where strategy work lives above {company}'s suite. Happy to show the architecture if the timing is better now.",
    ],
    "angle3": [
        "Following up on the indirect coverage gap. I can share the {industry} benchmark numbers first — useful even if the timing is off.",
        "Quick follow-up on spend under strategy at {company}. The benchmark for {industry} is one page — happy to send it with no strings attached.",
        "Last note was on the tail-spend strategy gap. I can share what the first 90 days usually looks like for teams in {industry}.",
    ],
}

T2_SUBJECTS: dict[str, list[str]] = {
    "angle1": [
        "Re: strategy cycle time at {company}",
        "Following up — category refresh at {company}",
        "One-pager on the strategy cycle gap",
    ],
    "angle2": [
        "Re: planning layer at {company}",
        "Following up — stack architecture",
        "One slide on the pre-sourcing gap",
    ],
    "angle3": [
        "Re: indirect coverage at {company}",
        "Following up — spend under strategy",
        "{industry} benchmark — no call needed",
    ],
}

# T3 social proof bodies — Day 7, 60-80w, secondary customer reference
T3_SOCIAL_PROOF_BODIES: dict[str, list[str]] = {
    "angle1": [
        "Tried twice on the strategy cycle at {company}, so I'll keep this short. Axpo's team was running 10-week refresh cycles across 15 categories; after Akirolabs the same output took days. Happy to put the one-pager together for {company} if useful.",
        "One more on the cycle time gap. Continental AG reduced strategy refresh cycles from quarterly to continuous updates across indirect categories. I can send the two-page overview.",
        "Third note on strategy speed. Schaeffler moved category planning from weeks to days across their indirect spend. The workflow is straightforward — happy to share it.",
    ],
    "angle2": [
        "Third note on the planning layer. Axpo runs Akirolabs as the strategy layer above the ERP suite they kept — no replacement, no migration. I can send the architecture diagram mapped to {company}.",
        "One more on the stack architecture. Merck's setup took four weeks to configure on top of their existing suite. I can share the integration overview.",
        "Third note on the pre-sourcing gap. Teams in {industry} typically run Akirolabs above their existing stack in under 30 days. I can send the onboarding overview.",
    ],
    "angle3": [
        "Third note on spend coverage. Raiffeisen Bank moved 60% of previously unmanaged indirect categories under formal strategy in one quarter. The first 90 days is a clear pattern — I can share the plan.",
        "One more on the coverage gap. {industry} teams typically cover 20-30% more spend under documented strategy in the first quarter. I can share the benchmark.",
        "Third note on tail spend. The biggest coverage gaps in {industry} are usually indirect services and IT contractors — I can share the category scan.",
    ],
}

T3_SUBJECTS: dict[str, list[str]] = {
    "angle1": [
        "One example on the strategy cycle",
        "How {company}-scale teams cut refresh time",
        "One case on category speed",
    ],
    "angle2": [
        "The stack setup that fits above {company}",
        "How teams keep the suite and add strategy",
        "One slide on the pre-sourcing layer",
    ],
    "angle3": [
        "One example on indirect coverage",
        "The first 90 days in {industry}",
        "Spend coverage case for {industry}",
    ],
}

# T5 break-up bodies — Day 15, 40-60w
BREAKUP_BODIES: dict[str, list[str]] = {
    "angle1": [
        "Last note on the category strategy cycle at {company}. If the timing is off or this isn't on the radar, no problem — I'll stop here and you can find me when it becomes relevant.",
        "Final one on the strategy refresh gap. If this isn't the right moment, feel free to ignore — I won't follow up again unless you reach back.",
        "Last note on cycle time. If the priority list has moved on, completely understood. I'll leave it here.",
    ],
    "angle2": [
        "Last note on the planning layer at {company}. If the stack is settled or the timing is wrong, no worries — I'll stop here.",
        "Final one on the pre-sourcing gap. If this isn't a priority at {company} right now, I'll leave it here and you can reach back when it is.",
        "Last note on the strategy layer. If you're not exploring this space, completely fine — I won't follow up again.",
    ],
    "angle3": [
        "Last note on the indirect coverage gap at {company}. If the portfolio is covered or the timing is off, no worries — I'll leave it here.",
        "Final one on spend under strategy. If this isn't on the agenda, completely understood. Feel free to reach back when it is.",
        "Last note on the category coverage. If the priorities are elsewhere, I'll stop here.",
    ],
}

T5_SUBJECTS: dict[str, list[str]] = {
    "angle1": [
        "Last note — strategy cycle at {company}",
        "Closing the loop on category refresh",
        "Final note on strategy speed",
    ],
    "angle2": [
        "Last note — planning layer at {company}",
        "Closing the loop on the stack gap",
        "Final note on pre-sourcing",
    ],
    "angle3": [
        "Last note — spend coverage at {company}",
        "Closing the loop on indirect strategy",
        "Final note on {industry} coverage",
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


def _build_akiro_sequence(
    angle_key: str,
    observation: str,
    company: str,
    industry: str,
    tier: int,
    persona: str,
    variant: int,
) -> OutreachSequence:
    """Build a 5-touch sequence (4 for Tier 3) for the recommended angle."""
    t1_body = _assemble_email(angle_key, observation, company, industry, variant)
    t1_subject = _assemble_subject(angle_key, company, variant)

    t2_body = FOLLOW_UP_BODIES[angle_key][variant].format(company=company, industry=industry)
    t2_subject = T2_SUBJECTS[angle_key][variant].format(company=company, industry=industry)

    t3_body = T3_SOCIAL_PROOF_BODIES[angle_key][variant].format(company=company, industry=industry)
    t3_subject = T3_SUBJECTS[angle_key][variant].format(company=company, industry=industry)

    t4_body = _assemble_dm(angle_key, observation, company, industry, variant)

    t5_body = BREAKUP_BODIES[angle_key][variant].format(company=company, industry=industry)
    t5_subject = T5_SUBJECTS[angle_key][variant].format(company=company, industry=industry)

    touches = [
        SequenceTouch(
            touch_number=1, day=0, channel="email",
            subject=t1_subject, body=t1_body, persona=persona,
            word_count=_word_count(t1_body),
        ),
        SequenceTouch(
            touch_number=2, day=3, channel="email",
            subject=t2_subject, body=t2_body, persona=persona,
            word_count=_word_count(t2_body),
        ),
        SequenceTouch(
            touch_number=3, day=7, channel="email",
            subject=t3_subject, body=t3_body, persona=persona,
            word_count=_word_count(t3_body),
        ),
        SequenceTouch(
            touch_number=4, day=10, channel="linkedin",
            body=t4_body, persona=persona,
            word_count=_word_count(t4_body),
        ),
        SequenceTouch(
            touch_number=5, day=15, channel="email",
            subject=t5_subject, body=t5_body, persona=persona,
            word_count=_word_count(t5_body),
        ),
    ]

    # Tier 3: drop social proof touch — shorter sequence for lower-priority accounts
    if tier >= 3:
        touches = [t for t in touches if t.touch_number != 3]
        for i, t in enumerate(touches):
            t.touch_number = i + 1

    return OutreachSequence(
        recommended_angle=angle_key,
        entry_persona=persona,
        touches=touches,
    )


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

    # Build multi-touch sequence for the recommended angle
    rec_angle = strategy.recommended_angle
    obs_map = {
        "angle1": obs.angle1_observation,
        "angle2": obs.angle2_observation,
        "angle3": obs.angle3_observation,
    }
    rec_obs = obs_map.get(rec_angle, obs.angle1_observation)
    tier = enrichment.icp.tier if enrichment.icp else 2
    angle_idx = list(ANGLE_KEYS).index(rec_angle) if rec_angle in ANGLE_KEYS else 0
    variant = _variant_index(company, angle_idx)
    sequence = _build_akiro_sequence(
        angle_key=rec_angle,
        observation=rec_obs,
        company=company,
        industry=industry,
        tier=tier,
        persona=strategy.cpo_hypothesis,
        variant=variant,
    )
    sequence = humanize_sequence(sequence)

    card = ProspectCard(
        before_after=_assemble_before_after(obs.before_text, obs.after_text),
        angles=angles,
        sequence=sequence,
    )
    trace.append("Humanizer: card assembled + 5-touch sequence + 29-rule filter applied")
    return {"card": card, "agent_trace": trace}
