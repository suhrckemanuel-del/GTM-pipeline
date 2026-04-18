"""
enrichment.py — Step 1: Enrichment Agent.

Three live actions:
  1. Exa search       -> recent news / triggers about the company
  2. Hunter.io search -> executive contacts (target: CPO / Head of Sourcing)
  3. LLM call         -> ICP Tier classification (1, 2, or 3) using structured output

Writes EnrichmentResult into the BDRState. Pure I/O + one structured-output LLM
call — no creative writing, no regex parsing.
"""
from __future__ import annotations

import os
from typing import List

import requests
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage

from .state import (
    BDRState,
    ContactLead,
    EnrichmentResult,
    ICPClassification,
    LiveSignal,
)

MODEL = "claude-sonnet-4-6"

EXA_QUERY_TEMPLATE = (
    "{company} procurement strategy OR supply chain OR sourcing OR earnings news"
)

PROCUREMENT_KEYWORDS = (
    "procurement", "sourcing", "supply chain", "supplier", "spend",
    "category management", "purchasing", "vendor",
)


# ---------------------------------------------------------------------------
# Exa
# ---------------------------------------------------------------------------
def _fetch_exa_signals(company: str, num_results: int = 5) -> List[LiveSignal]:
    api_key = os.environ.get("EXA_API_KEY", "")
    if not api_key:
        return []
    try:
        from exa_py import Exa  # type: ignore
    except ImportError:
        return []

    try:
        exa = Exa(api_key=api_key)
        results = exa.search_and_contents(
            EXA_QUERY_TEMPLATE.format(company=company),
            num_results=num_results,
            use_autoprompt=True,
            text={"max_characters": 600},
        )
    except Exception:
        try:
            exa = Exa(api_key=api_key)
            results = exa.search(
                EXA_QUERY_TEMPLATE.format(company=company),
                num_results=num_results,
                use_autoprompt=True,
            )
        except Exception:
            return []

    signals: List[LiveSignal] = []
    for r in (results.results or [])[:num_results]:
        title = (getattr(r, "title", "") or "").strip()
        url = (getattr(r, "url", "") or "").strip()
        snippet = (getattr(r, "text", "") or "").strip()
        if title or snippet:
            signals.append(LiveSignal(title=title, url=url, snippet=snippet[:600]))
    return signals


# ---------------------------------------------------------------------------
# Hunter.io
# ---------------------------------------------------------------------------
def _fetch_hunter_contacts(company: str, limit: int = 10) -> tuple[str, List[ContactLead]]:
    """
    Returns (resolved_domain, contacts).

    Strategy: use Hunter's domain-search with company= autocomplete and pull
    executive-level emails. Filter to procurement-flavoured positions where
    possible; otherwise return the top exec list.
    """
    api_key = os.environ.get("HUNTER_API_KEY", "")
    if not api_key:
        return "", []

    try:
        resp = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={
                "company": company,
                "seniority": "senior,executive",
                "limit": limit,
                "api_key": api_key,
            },
            timeout=15,
        )
    except requests.RequestException:
        return "", []

    if resp.status_code != 200:
        return "", []

    data = (resp.json() or {}).get("data") or {}
    domain = (data.get("domain") or "").strip()
    emails = data.get("emails") or []

    contacts: List[ContactLead] = []
    procurement_hits: List[ContactLead] = []
    for e in emails:
        position = (e.get("position") or "").strip()
        first = (e.get("first_name") or "").strip()
        last = (e.get("last_name") or "").strip()
        full = f"{first} {last}".strip()
        lead = ContactLead(
            name=full,
            email=(e.get("value") or "").strip(),
            position=position,
            seniority=(e.get("seniority") or "").strip(),
            department=(e.get("department") or "").strip(),
            confidence=int(e.get("confidence") or 0),
        )
        contacts.append(lead)
        if any(k in position.lower() for k in PROCUREMENT_KEYWORDS):
            procurement_hits.append(lead)

    # Prefer procurement matches if any, else fall back to top-confidence execs
    if procurement_hits:
        return domain, procurement_hits[:5]
    contacts.sort(key=lambda c: c.confidence, reverse=True)
    return domain, contacts[:5]


# ---------------------------------------------------------------------------
# ICP Tier classification (structured output)
# ---------------------------------------------------------------------------
ICP_SYSTEM = """\
You are the ICP-tier classifier for Akirolabs (a category-strategy automation \
platform for large enterprise procurement).

Tiers:
  - Tier 1: Strategic enterprise. Revenue >= ~€5B OR headcount >= ~50k. Multi-division \
or multi-country procurement organisation. Best long-term ACV.
  - Tier 2: Mid-large. Revenue €1-5B OR headcount 10-50k. Single CPO + small team.
  - Tier 3: Below those bands or unclear scale. Less likely fit today.

Use any clues in the research summary (regions, divisions, revenue, headcount, \
listed status) to make your call. Be decisive — pick exactly one tier."""


def _classify_icp(company: str, industry: str, summary: str) -> ICPClassification:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ICPClassification(
            tier=2,
            tier_label="Tier 2 — unverified (no API key)",
            rationale="ANTHROPIC_API_KEY missing.",
        )
    llm = ChatAnthropic(model=MODEL, api_key=api_key, max_tokens=400, temperature=0.0)
    structured = llm.with_structured_output(ICPClassification)
    user = (
        f"Company: {company}\n"
        f"Industry: {industry or 'unknown'}\n\n"
        f"Research summary:\n{summary or '(no signals available)'}\n\n"
        "Classify this account into Tier 1, 2, or 3 for Akirolabs."
    )
    try:
        result: ICPClassification = structured.invoke(
            [SystemMessage(content=ICP_SYSTEM), HumanMessage(content=user)]
        )
    except Exception:
        return ICPClassification(
            tier=2,
            tier_label="Tier 2 — classification failed",
            rationale="LLM classification call failed.",
        )
    if result.tier not in (1, 2, 3):
        result.tier = 2
    if not result.tier_label:
        labels = {1: "Tier 1 — Strategic Enterprise", 2: "Tier 2 — Mid-Large", 3: "Tier 3 — Below band"}
        result.tier_label = labels[result.tier]
    return result


# ---------------------------------------------------------------------------
# Research summary (CPO lens) — same lightweight LLM pass as v2.0 Researcher
# ---------------------------------------------------------------------------
RESEARCH_SYSTEM = """\
You are the Research Agent in a B2B sales workflow for Akirolabs.

Read the provided live signals and contact list. Summarise what matters \
specifically to a Chief Procurement Officer / Head of Strategic Sourcing at \
this company:
  - What is changing in their spend, supply base, or operating model?
  - What time / cost / coverage pressures sit on category strategy work today?
  - Anything in the public signals hinting at procurement disruption?

3-5 short bullets. No marketing language. If signals are thin, say so plainly."""


def _summarise(company: str, industry: str, signals: List[LiveSignal], contacts: List[ContactLead]) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return "ANTHROPIC_API_KEY missing — no LLM summary available."

    sig_block = "\n\n".join(
        f"[{i+1}] {s.title}\n  URL: {s.url}\n  {s.snippet}"
        for i, s in enumerate(signals)
    ) or "(no signals)"

    contact_block = "\n".join(
        f"- {c.name or '(no name)'} — {c.position or 'unknown role'} ({c.email or 'no email'})"
        for c in contacts
    ) or "(no contacts found)"

    user = (
        f"Company: {company}\n"
        f"Industry: {industry or 'unknown'}\n\n"
        f"Live signals (Exa):\n{sig_block}\n\n"
        f"Contacts (Hunter.io):\n{contact_block}\n\n"
        "Summarise through the CPO lens."
    )
    llm = ChatAnthropic(model=MODEL, api_key=api_key, max_tokens=600, temperature=0.2)
    try:
        resp = llm.invoke([SystemMessage(content=RESEARCH_SYSTEM), HumanMessage(content=user)])
    except Exception as exc:
        return f"(summary failed: {exc})"
    content = resp.content
    if isinstance(content, str):
        return content.strip()
    return "".join(c.get("text", "") for c in content if isinstance(c, dict)).strip()


# ---------------------------------------------------------------------------
# LangGraph node
# ---------------------------------------------------------------------------
def run_enrichment(state: BDRState) -> dict:
    """LangGraph node — runs the 3 enrichment actions in sequence."""
    company = state.get("company", "").strip()
    industry = state.get("industry", "").strip()
    trace = list(state.get("agent_trace", []))

    if not company:
        return {"error": "Enrichment: company name is required.", "agent_trace": trace}

    trace.append("Enrichment: fetching live triggers via Exa")
    signals = _fetch_exa_signals(company)
    trace.append(f"Enrichment: {len(signals)} Exa signals retrieved")

    trace.append("Enrichment: pulling executive contacts via Hunter.io")
    domain, contacts = _fetch_hunter_contacts(company)
    trace.append(
        f"Enrichment: {len(contacts)} Hunter contacts" + (f" @ {domain}" if domain else "")
    )

    trace.append("Enrichment: synthesising research summary")
    summary = _summarise(company, industry, signals, contacts)

    trace.append("Enrichment: classifying ICP tier")
    icp = _classify_icp(company, industry, summary)
    trace.append(f"Enrichment: ICP {icp.tier_label}")

    enrichment = EnrichmentResult(
        company=company,
        industry=industry,
        domain=domain,
        live_signals=signals,
        contacts=contacts,
        research_summary=summary,
        icp=icp,
    )
    return {"enrichment": enrichment, "agent_trace": trace}
