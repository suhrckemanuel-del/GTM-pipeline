"""
gleef_humanizer.py — Humanizer Drafter for Gleef BDR pipeline.

Same anti-AI pattern as the Akirolabs humanizer:
  - LLM produces ONLY short observations (GleefObservations structured schema)
  - Proof points, pain amplifiers, sequence templates come from fixed string banks
  - Output: ProspectCard with a full OutreachSequence (5 touches over 15 days)

Sequence structure (PAS-driven, industry-grade):
  Touch 1  Day  0  Email     Pain hook (PAS formula)
  Touch 2  Day  3  Email     Short follow-up with new hook (40-60 words)
  Touch 3  Day  7  Email     Social proof, different observation
  Touch 4  Day 10  LinkedIn  Provocative question, no hard ask
  Touch 5  Day 15  Email     Break-up with free plugin CTA

Tier 3 accounts get 4 touches (Touch 3 dropped).
"""
from __future__ import annotations

import os
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.services.humanizer_rules import humanize_sequence, humanize_angle_draft

from .state import (
    AngleDraft,
    BDRState,
    OutreachSequence,
    ProspectCard,
    SequenceTouch,
)

MODEL = "claude-sonnet-4-6"

GLEEF_ANGLE_KEYS = ("angle1", "angle2", "angle3")

GLEEF_ANGLE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "angle1": {"name": "Figma-Native Workflow", "tab_label": "Figma-Native"},
    "angle2": {"name": "Developer Experience", "tab_label": "Dev Experience"},
    "angle3": {"name": "Brand Voice at Scale", "tab_label": "Brand Voice"},
}

GLEEF_PERSONA_MAP = {
    "angle1": "VP Product / Head of Product",
    "angle2": "VP Engineering / Head of Engineering",
    "angle3": "Head of Design / UX Lead",
}

SECONDARY_OBS_KEY = {
    "angle1": "angle2_observation",
    "angle2": "angle3_observation",
    "angle3": "angle1_observation",
}


# ---------------------------------------------------------------------------
# Fixed string banks
# ---------------------------------------------------------------------------
GLEEF_ANGLE_PROOFS: dict[str, list[str]] = {
    "angle1": [
        "Alan (970K members, France's fastest-growing health insurer) moved their entire "
        "translation review into Figma — designers validate every string before a line of code ships.",
        "One European SaaS team cut their design-to-translated-feature cycle from 2 days to "
        "under 2 hours after moving localization review into Figma.",
        "A Series B product team went from four tool switches per localization sprint to one — "
        "Figma is now where it starts and ends.",
    ],
    "angle2": [
        "Alan's engineering team eliminated manual key cleanup entirely — Gleef generates "
        "context-aware names from the actual design, not frame IDs like Frame15034.",
        "One engineering lead plugged Gleef CLI into their CI/CD pipeline and shipped their "
        "first German localisation with zero additional dev sprints.",
        "A product engineering team went from 'i18n is the thing everyone dreads' to "
        "'it's just another git push' — same pipeline, no rework.",
    ],
    "angle3": [
        "Alan maintains brand voice across French, English, and Spanish without a dedicated "
        "localisation manager — Gleef's AI memory learns their UX writing rules once.",
        "One B2B SaaS scaled from 2 to 7 languages in a single quarter without a localisation "
        "agency — Gleef carried their brand guidelines into every market.",
        "A UX lead put it directly: 'Crowdin gave us accurate translations. "
        "Gleef gives us translations that sound like us.'",
    ],
}

EMAIL_OFFERS: dict[str, list[str]] = {
    "angle1": [
        "I can walk through the Figma workflow and map it to {company}.",
        "I can show how that review cycle works and where it fits {company}'s sprint.",
        "I can send a walkthrough and map it to {company}'s current design-to-dev flow.",
    ],
    "angle2": [
        "I can show the CLI setup and map it to {company}'s pipeline.",
        "I can share the engineering workflow and where the same setup fits {company}.",
        "I can send the technical walkthrough and map it to {company}'s stack.",
    ],
    "angle3": [
        "I can share how the brand voice memory works and map it to {company}.",
        "I can walk through the brand guidelines setup and show where {company} would start.",
        "I can send the brand voice configuration and show how it applies at {company}.",
    ],
}

PAIN_AMPLIFIERS: dict[str, str] = {
    "angle1": (
        "That usually means translations are reviewed without seeing the actual layout — "
        "designers catch broken strings after dev, not before."
    ),
    "angle2": (
        "That usually means i18n keys pile up with no naming convention and developers "
        "spend sprint time on cleanup that adds zero product value."
    ),
    "angle3": (
        "That usually means translations are accurate but off-brand — "
        "the tone that took years to build disappears between languages."
    ),
}

FOLLOW_UP_HOOKS: dict[str, list[str]] = {
    "angle1": [
        "Wanted to add context: the biggest friction most product teams flag isn't the "
        "translation itself — it's the review cycle after, when designers see broken layouts "
        "in staging.",
        "One thing worth knowing: Gleef's localization preview updates in real-time inside "
        "Figma — your designers see the exact layout impact of each translation before code.",
        "Quick follow-on from my last note: teams seeing the biggest gains are the ones "
        "where design and dev share one tool, not hand off between two.",
    ],
    "angle2": [
        "Worth adding: Gleef CLI hooks directly into the git workflow — no separate "
        "export/import step, just a command that syncs translations on push.",
        "One thing I should have mentioned: Gleef generates i18n keys from design context, "
        "not frame names — Alan's team called it the first thing that 'actually worked'.",
        "Quick follow-up: the engineering teams getting the most value are the ones where "
        "the CLI removes localisation from the critical path entirely.",
    ],
    "angle3": [
        "One thing I didn't mention: Gleef's AI memory learns from your existing copy — "
        "it doesn't just translate, it applies your actual UX writing rules.",
        "Worth adding: brand guidelines you've already documented can be loaded into Gleef "
        "directly — it's not a rethink, it's a transfer.",
        "Quick follow-up: teams maintaining the strongest brand voice across markets are "
        "the ones where UX writers set the rules once and Gleef applies them everywhere.",
    ],
}

T1_SUBJECTS: dict[str, list[str]] = {
    "angle1": [
        "Localization review pulling your designers into a second tool?",
        "Translation review without the layout context",
        "Figma-first localisation at {company}",
    ],
    "angle2": [
        "i18n keys named Frame15034 at {company}?",
        "Localisation outside the git workflow",
        "Developer i18n friction at {company}",
    ],
    "angle3": [
        "Does your translated UI still sound like {company}?",
        "Brand voice across languages at {company}",
        "Localisation at {company} — brand voice question",
    ],
}

SOCIAL_PROOF_SUBJECTS: dict[str, list[str]] = {
    "angle1": [
        "How teams cut localisation review out of the sprint",
        "Design-to-translated: one tool instead of four",
        "Localisation review in Figma — how Alan does it",
    ],
    "angle2": [
        "i18n keys from design context — how engineering teams are doing it",
        "CLI-based localisation that fits the git workflow",
        "How one team eliminated i18n debt from their sprint",
    ],
    "angle3": [
        "Brand voice across 7 languages — how one team manages it",
        "Translations that sound like you — the setup behind it",
        "How Alan maintains tone consistency without a localisation manager",
    ],
}

LINKEDIN_DM_QUESTIONS: dict[str, list[str]] = {
    "angle1": [
        "Quick question — when {company} ships a new feature, how many tool switches does "
        "the localisation review add before the design is final?",
        "Curious about something: how does your team currently handle translation review for "
        "new UI? Are designers in the loop before dev picks it up?",
        "One thing I've been benchmarking across product teams: how long does localisation "
        "add to the average feature cycle? The numbers surprise most people.",
    ],
    "angle2": [
        "Quick question — how does your team currently manage i18n keys? We've been tracking "
        "naming convention debt across engineering teams and the pattern is pretty consistent.",
        "Curious about {company}'s setup: is your localisation workflow integrated into "
        "CI/CD, or does it live outside the pipeline?",
        "One thing I've been asking engineering leads: what's the most annoying part of your "
        "current i18n workflow? The answers are almost always the same.",
    ],
    "angle3": [
        "Quick question — when {company} translates UI copy, how do you make sure brand "
        "voice carries across languages? Most teams have a bigger gap here than they expect.",
        "Curious about {company}'s localisation: is there someone on your team responsible "
        "for brand consistency across languages, or does it happen after translation?",
        "One thing I've been tracking: how much time UX writers spend reviewing translated "
        "copy for brand alignment. Worth knowing the benchmark?",
    ],
}

BREAKUP_BODIES: dict[str, list[str]] = {
    "angle1": [
        "Not going to keep following up — clearly timing isn't right. If getting your design "
        "team into the localisation review loop becomes a priority, I'm easy to find.\n\n"
        "One thing worth knowing: Gleef's free Figma plugin lets your team preview exactly "
        "what I'm describing — zero commitment, live in 10 minutes. gleef.eu/figma-plugin",
        "Closing the loop here. If multilingual shipping velocity becomes a priority, "
        "reach back whenever.\n\n"
        "For reference: Gleef's Figma plugin is free to try. gleef.eu/figma-plugin",
        "Won't keep reaching out. If the design-to-localisation handoff becomes a bottleneck "
        "later, happy to help.\n\nFree plugin: gleef.eu/figma-plugin",
    ],
    "angle2": [
        "Not going to keep following up. If i18n workflow friction becomes something your "
        "team wants to tackle, I'm easy to find.\n\n"
        "For reference: Gleef CLI is free to try — your devs can see the key generation and "
        "sync workflow without any sales conversation. docs.gleef.eu/cli",
        "Closing this thread. If localisation pipeline cleanup ever becomes a priority, "
        "reach back anytime.\n\nFree CLI docs: docs.gleef.eu/cli",
        "Won't keep reaching out. If the i18n overhead becomes worth solving, happy to "
        "talk then.\n\nFree trial: gleef.eu",
    ],
    "angle3": [
        "Not going to keep following up. If brand voice consistency across markets becomes "
        "a priority, I'm easy to reach.\n\n"
        "For reference: Gleef's Figma plugin is free — your UX writers can see how the "
        "brand memory works without a sales conversation. gleef.eu/figma-plugin",
        "Closing the loop here. If maintaining brand voice at scale becomes worth tackling, "
        "reach back anytime.\n\nFree plugin: gleef.eu/figma-plugin",
        "Won't keep reaching out. If tone consistency across languages becomes a bottleneck, "
        "happy to help then.\n\nFree trial: gleef.eu",
    ],
}

BREAKUP_SUBJECTS: list[str] = [
    "Before I close this out",
    "Closing the loop — {company}",
    "Last note from me",
]


# ---------------------------------------------------------------------------
# Gleef-specific LLM observation schema (local — not in state.py)
# ---------------------------------------------------------------------------
class GleefObservations(BaseModel):
    angle1_observation: str = Field(
        description=(
            "One sentence (max ~20 words) naming the specific Figma-to-dev localisation "
            "friction at this company. Name the actual product, market, or workflow step."
        )
    )
    angle2_observation: str = Field(
        description=(
            "One sentence (max ~20 words) naming the specific i18n key or developer "
            "workflow pain at this company."
        )
    )
    angle3_observation: str = Field(
        description=(
            "One sentence (max ~20 words) naming the specific brand voice consistency "
            "challenge across their markets or languages."
        )
    )
    before_text: str = Field(
        description=(
            "One short paragraph: how this company likely does localisation today. "
            "Concrete pain. Reference their actual markets or languages if known."
        )
    )
    after_text: str = Field(
        description=(
            "One short paragraph on Gleef's impact. Mention: translations preview in Figma "
            "before dev, AI memory applies brand voice, CLI fits the git workflow. "
            "Do NOT start with 'With Gleef:' — the assembler prepends that prefix."
        )
    )


OBSERVATION_SYSTEM = """\
You are the Observation Generator for the Gleef Humanizer agent.

You are NOT writing emails. You produce 5 short text snippets the deterministic \
assembler glues into templates using fixed proof banks.

Rules:
  - No buzzwords: never use "leverage", "transformative", "cutting-edge", "seamlessly", \
"revolutionize", "streamline" (as verb), "empower", "ecosystem", "unlock".
  - No rhetorical openers or questions.
  - Each observation: ONE sentence, max ~20 words.
  - Name the actual product, market, language pair, or workflow step creating friction.
  - Before/After: short paragraphs. After must NOT start with "With Gleef:" — the \
assembler prepends it. After should mention: preview in Figma, AI brand memory, CLI."""


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------
def _clean(text: str) -> str:
    cleaned = (text or "").replace("—", ", ")
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


def _variant_index(company: str, angle_idx: int) -> int:
    return (sum(ord(c) for c in company.lower()) + angle_idx) % 3


# ---------------------------------------------------------------------------
# LLM observation call
# ---------------------------------------------------------------------------
def _generate_gleef_observations(
    company: str,
    industry: str,
    research_summary: str,
    pain_signal: str,
    persona: str,
) -> GleefObservations:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return GleefObservations(
            angle1_observation=f"{company} reviews translated UI outside Figma, after design is finalised.",
            angle2_observation=f"{company}'s developers manage i18n keys manually outside the git workflow.",
            angle3_observation=f"{company}'s translated UI copy loses brand tone across languages.",
            before_text=f"{company} handles localisation through a separate tool after design handoff, stripping context from translations.",
            after_text="translations preview in Figma before a line of code ships, Gleef's AI memory applies brand guidelines across all languages, and the CLI fits directly into the existing git workflow.",
        )

    llm = ChatAnthropic(model=MODEL, api_key=api_key, max_tokens=900, temperature=0.4)
    structured = llm.with_structured_output(GleefObservations)

    user = (
        f"Company: {company}\n"
        f"Industry: {industry or 'unknown'}\n"
        f"Target persona: {persona}\n"
        f"Specific pain signal: {pain_signal}\n\n"
        f"Research summary:\n{research_summary or '(none)'}\n\n"
        "Produce GleefObservations: three one-sentence observations (one per angle) "
        "and the two-paragraph Before/After. Be concrete and specific."
    )
    try:
        return structured.invoke(
            [SystemMessage(content=OBSERVATION_SYSTEM), HumanMessage(content=user)]
        )
    except Exception:
        return GleefObservations(
            angle1_observation=f"{company} reviews translated UI outside Figma, after design is finalised.",
            angle2_observation=f"{company}'s developers manage i18n keys manually outside the git workflow.",
            angle3_observation=f"{company}'s translated UI loses brand tone between languages.",
            before_text=f"{company} handles localisation through a separate tool after design handoff.",
            after_text="translations preview in Figma before code ships, AI memory applies brand voice, CLI integrates with git.",
        )


# ---------------------------------------------------------------------------
# Touch assemblers
# ---------------------------------------------------------------------------
def _assemble_t1_email(
    angle_key: str, observation: str, company: str, industry: str, variant: int
) -> str:
    p1 = _clean(observation)
    p2 = PAIN_AMPLIFIERS[angle_key]
    p3 = GLEEF_ANGLE_PROOFS[angle_key][variant]
    offer = EMAIL_OFFERS[angle_key][variant].format(company=company, industry=industry)
    p4 = f"{offer} Tuesday 1 pm or Wednesday 10 am for 15 minutes?"

    email = "\n\n".join([p1, p2, p3, p4]) + "\n\nManuel Suhrcke"
    wc = _word_count(email)
    if wc > 110:
        p1 = _trim_words(p1, max(12, len(p1.split()) - (wc - 100)))
        email = "\n\n".join([p1, p2, p3, p4]) + "\n\nManuel Suhrcke"
    return email


def _assemble_t2_email(angle_key: str, variant: int) -> str:
    hook = FOLLOW_UP_HOOKS[angle_key][variant]
    cta = (
        "Happy to send a 2-min Loom instead if a call feels like too much — "
        "just reply with 'Loom' and I'll send it over."
    )
    return f"{hook}\n\n{cta}\n\nManuel Suhrcke"


def _assemble_t3_email(
    angle_key: str, secondary_obs: str, company: str, industry: str, variant: int
) -> str:
    proof_variant = (variant + 1) % 3
    p1 = _clean(secondary_obs)
    p2 = GLEEF_ANGLE_PROOFS[angle_key][proof_variant]
    offer = EMAIL_OFFERS[angle_key][proof_variant].format(company=company, industry=industry)
    p3 = f"{offer} Tuesday 1 pm or Wednesday 10 am?"

    email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
    wc = _word_count(email)
    if wc > 100:
        p1 = _trim_words(p1, max(10, len(p1.split()) - (wc - 90)))
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
    return email


def _assemble_t4_dm(angle_key: str, company: str, variant: int) -> str:
    q = LINKEDIN_DM_QUESTIONS[angle_key][variant].format(company=company)
    dm = f"{q}\n\nManuel"
    if _word_count(dm) > 60:
        dm = f"{_trim_words(q, 50)}\n\nManuel"
    return dm


def _assemble_t5_breakup(angle_key: str, company: str, variant: int) -> str:
    body = BREAKUP_BODIES[angle_key][variant].format(company=company)
    return f"{body}\n\nManuel Suhrcke"


def _assemble_before_after(before: str, after: str) -> str:
    before = _clean(before)
    after = _clean(after)
    after = re.sub(r"^\s*With Gleef:\s*", "", after, flags=re.I)
    return f"{before}\n\nWith Gleef: {after}"


# ---------------------------------------------------------------------------
# Sequence builder
# ---------------------------------------------------------------------------
def _build_gleef_sequence(
    angle_key: str,
    obs: GleefObservations,
    company: str,
    industry: str,
    persona: str,
    tier: int,
) -> OutreachSequence:
    angle_idx = GLEEF_ANGLE_KEYS.index(angle_key)
    variant = _variant_index(company, angle_idx)

    primary_obs = getattr(obs, f"{angle_key}_observation")
    secondary_obs_attr = SECONDARY_OBS_KEY[angle_key]
    secondary_obs = getattr(obs, secondary_obs_attr)

    t1_subj = T1_SUBJECTS[angle_key][variant].format(company=company)
    t2_subj = f"Re: {t1_subj}"
    t3_subj = SOCIAL_PROOF_SUBJECTS[angle_key][variant]
    t5_subj = BREAKUP_SUBJECTS[variant].format(company=company)

    t1_body = _assemble_t1_email(angle_key, primary_obs, company, industry, variant)
    t2_body = _assemble_t2_email(angle_key, variant)
    t3_body = _assemble_t3_email(angle_key, secondary_obs, company, industry, variant)
    t4_body = _assemble_t4_dm(angle_key, company, variant)
    t5_body = _assemble_t5_breakup(angle_key, company, variant)

    all_touches = [
        SequenceTouch(
            touch_number=1, day=0, channel="email",
            subject=t1_subj, body=t1_body, cta="15-min call",
            persona=persona, word_count=_word_count(t1_body),
        ),
        SequenceTouch(
            touch_number=2, day=3, channel="email",
            subject=t2_subj, body=t2_body, cta="Loom or call",
            persona=persona, word_count=_word_count(t2_body),
        ),
        SequenceTouch(
            touch_number=3, day=7, channel="email",
            subject=t3_subj, body=t3_body, cta="15-min call",
            persona=persona, word_count=_word_count(t3_body),
        ),
        SequenceTouch(
            touch_number=4, day=10, channel="linkedin",
            subject="", body=t4_body, cta="Engage",
            persona=persona, word_count=_word_count(t4_body),
        ),
        SequenceTouch(
            touch_number=5, day=15, channel="email",
            subject=t5_subj, body=t5_body, cta="Free plugin",
            persona=persona, word_count=_word_count(t5_body),
        ),
    ]

    # Tier 3: drop social proof touch to keep sequence lighter
    if tier == 3:
        touches = [t for t in all_touches if t.touch_number != 3]
        for i, t in enumerate(touches):
            t.touch_number = i + 1
    else:
        touches = all_touches

    return OutreachSequence(
        recommended_angle=angle_key,
        entry_persona=persona,
        touches=touches,
    )


def _build_gleef_angle(
    angle_key: str, observation: str, company: str, industry: str
) -> AngleDraft:
    angle_idx = GLEEF_ANGLE_KEYS.index(angle_key)
    variant = _variant_index(company, angle_idx)
    meta = GLEEF_ANGLE_DESCRIPTIONS[angle_key]
    return AngleDraft(
        angle_key=angle_key,
        name=meta["name"],
        tab_label=meta["tab_label"],
        dm=_assemble_t4_dm(angle_key, company, variant),
        email_subject=T1_SUBJECTS[angle_key][variant].format(company=company),
        email_body=_assemble_t1_email(angle_key, observation, company, industry, variant),
    )


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def run_gleef_humanizer(state: BDRState) -> dict:
    if state.get("error"):
        return {}

    enrichment = state.get("enrichment")
    strategy = state.get("strategy")
    if not enrichment or not strategy:
        return {"error": "Gleef Humanizer: missing enrichment or strategy."}

    trace = list(state.get("agent_trace", []))
    trace.append("Humanizer: generating Gleef observations under strict schema")

    obs = _generate_gleef_observations(
        company=enrichment.company,
        industry=enrichment.industry,
        research_summary=enrichment.research_summary,
        pain_signal=strategy.pain_signal,
        persona=strategy.cpo_hypothesis,
    )

    trace.append("Humanizer: assembling 5-touch outreach sequence via fixed banks")
    company = enrichment.company
    industry = enrichment.industry or "SaaS"
    angle_key = strategy.recommended_angle
    if angle_key not in GLEEF_ANGLE_KEYS:
        angle_key = "angle1"
    tier = enrichment.icp.tier if enrichment.icp else 2

    sequence = _build_gleef_sequence(
        angle_key=angle_key,
        obs=obs,
        company=company,
        industry=industry,
        persona=strategy.cpo_hypothesis,
        tier=tier,
    )
    sequence = humanize_sequence(sequence)

    angles = [
        humanize_angle_draft(_build_gleef_angle("angle1", obs.angle1_observation, company, industry)),
        humanize_angle_draft(_build_gleef_angle("angle2", obs.angle2_observation, company, industry)),
        humanize_angle_draft(_build_gleef_angle("angle3", obs.angle3_observation, company, industry)),
    ]

    card = ProspectCard(
        before_after=_assemble_before_after(obs.before_text, obs.after_text),
        angles=angles,
        sequence=sequence,
    )

    n = len(sequence.touches)
    last_day = sequence.touches[-1].day
    trace.append(
        f"Humanizer: {n}-touch sequence ({last_day}-day window) → {strategy.cpo_hypothesis}"
    )
    return {"card": card, "agent_trace": trace}
