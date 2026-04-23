"""
state.py — Shared state and Pydantic schemas for the V2 BDR multi-agent workflow.

The BDRState dict is the single object passed between LangGraph nodes:

    Enrichment  ->  Strategist  ->  Humanizer  ->  CRM Sync

Each agent reads from the state, mutates one slice, and returns a partial dict
that LangGraph merges in. Pydantic models give us guaranteed JSON schemas for
the LLM tool calls — no regex parsing anywhere.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Constants reused across agents
# ---------------------------------------------------------------------------
ANGLE_KEYS = ("angle1", "angle2", "angle3")

ANGLE_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "angle1": {
        "name": "Strategy Speed Gap",
        "tab_label": "Speed Gap",
        "description": (
            "Strategy Speed Gap: long manual category strategy refresh cycles, "
            "leadership pressure to move faster, transformation programmes."
        ),
    },
    "angle2": {
        "name": "Suite Fatigue Wedge",
        "tab_label": "Suite Fatigue",
        "description": (
            "Suite Fatigue Wedge: heavy ERP / spend-analytics suite already in place "
            "but no automation of category strategy narrative or stakeholder decks."
        ),
    },
    "angle3": {
        "name": "Unmanaged Spend Trigger",
        "tab_label": "Spend Trigger",
        "description": (
            "Unmanaged Spend Trigger: tail-spend or indirect categories growing "
            "without a documented strategy, analyst bandwidth constraint."
        ),
    },
}


# ---------------------------------------------------------------------------
# Enrichment schemas — Exa + Hunter.io + ICP
# ---------------------------------------------------------------------------
class LiveSignal(BaseModel):
    """A single live web signal pulled from Exa."""
    title: str = ""
    url: str = ""
    snippet: str = ""


class ContactLead(BaseModel):
    """A single contact pulled from Hunter.io domain search."""
    name: str = ""
    email: str = ""
    position: str = ""
    seniority: str = ""
    department: str = ""
    confidence: int = 0


class ICPClassification(BaseModel):
    """The Enrichment agent's ICP-tier judgement."""
    tier: int = Field(
        description=(
            "1, 2, or 3. Tier 1 = strategic enterprise (>=€5B revenue or >=50k headcount). "
            "Tier 2 = mid-large (€1-5B / 10-50k). Tier 3 = below that band."
        )
    )
    tier_label: str = Field(description="Human label, e.g. 'Tier 1 — Strategic Enterprise'.")
    rationale: str = Field(description="One sentence justifying the tier.")


class EnrichmentResult(BaseModel):
    """Output of the Enrichment agent."""
    company: str
    industry: str
    domain: str = ""
    live_signals: List[LiveSignal] = []
    contacts: List[ContactLead] = []
    icp: Optional[ICPClassification] = None
    research_summary: str = Field(
        default="", description="LLM-synthesised view of the live signals through the CPO lens."
    )


# ---------------------------------------------------------------------------
# Strategist schema
# ---------------------------------------------------------------------------
class StrategyDecision(BaseModel):
    """The Strategist agent's output — chosen angle plus rationale."""
    recommended_angle: str = Field(
        description="One of: angle1 (Strategy Speed Gap), angle2 (Suite Fatigue Wedge), angle3 (Unmanaged Spend Trigger)."
    )
    angle_name: str = Field(description="Human-readable name of the chosen angle.")
    rationale: str = Field(
        description="2-3 sentences explaining why this angle fits — grounded in enrichment data."
    )
    cpo_hypothesis: str = Field(
        description="Likely title of the procurement decision-maker."
    )
    pain_signal: str = Field(
        description="One sentence naming the specific category strategy pain at this company today."
    )


# ---------------------------------------------------------------------------
# Humanizer schemas
# ---------------------------------------------------------------------------
class HumanizerObservations(BaseModel):
    """
    LLM-only output from the Humanizer agent.

    The LLM produces ONLY short, specific observations (one per angle) and the
    Before/After narrative. Proof points and offer templates come from fixed
    string banks — not from creative LLM writing. This is the anti-AI guarantee.
    """
    angle1_observation: str = Field(
        description="One sentence (max ~22 words) naming the speed-gap pain at this company. No fluff."
    )
    angle2_observation: str = Field(
        description="One sentence (max ~22 words) naming the suite-fatigue gap at this company."
    )
    angle3_observation: str = Field(
        description="One sentence (max ~22 words) naming the unmanaged-spend / coverage gap."
    )
    before_text: str = Field(
        description="One short paragraph: how this company runs category strategy today. Concrete pain."
    )
    after_text: str = Field(
        description="One short paragraph (without the 'With Akirolabs:' prefix — the UI prepends it)."
    )


class AngleDraft(BaseModel):
    """Final assembled draft for one angle."""
    angle_key: str
    name: str
    tab_label: str
    dm: str
    email_subject: str
    email_body: str


class SequenceTouch(BaseModel):
    """One touch in a multi-step outreach sequence."""
    touch_number: int
    day: int
    channel: str  # "email" | "linkedin"
    subject: str = ""
    body: str = ""
    cta: str = ""
    persona: str = ""
    word_count: int = 0


class OutreachSequence(BaseModel):
    """Full multi-touch sequence for one prospect."""
    recommended_angle: str
    entry_persona: str
    touches: List[SequenceTouch]


class ProspectCard(BaseModel):
    """Final assembled card — Before/After + 3 angle drafts + optional sequence."""
    before_after: str
    angles: List[AngleDraft]
    sequence: Optional[OutreachSequence] = None


# ---------------------------------------------------------------------------
# CRM sync schema
# ---------------------------------------------------------------------------
class CRMSyncResult(BaseModel):
    """Output of the Notion CRM connector."""
    success: bool
    page_id: str = ""
    page_url: str = ""
    error: str = ""
    skipped: bool = False
    skip_reason: str = ""


# ---------------------------------------------------------------------------
# BDRState — the shared mutable state passed between LangGraph nodes
# ---------------------------------------------------------------------------
class BDRState(TypedDict, total=False):
    """
    Filled in progressively across the 4 nodes.

    Inputs:        company, industry, sync_to_notion (bool flag from UI)
    Enrichment:    enrichment (EnrichmentResult)
    Strategist:    strategy   (StrategyDecision)
    Humanizer:     card       (ProspectCard)
    CRM Sync:      crm_result (CRMSyncResult)
    Any agent:     error      (terminates the workflow)
    Trace:         agent_trace (list of "Agent: status" strings for the UI)
    """
    company: str
    industry: str
    sync_to_notion: bool
    enrichment: EnrichmentResult
    strategy: StrategyDecision
    card: ProspectCard
    crm_result: CRMSyncResult
    error: Optional[str]
    agent_trace: List[str]
