"""
gleef_workflow.py — LangGraph orchestrator for the Gleef BDR pipeline.

Reuses company-agnostic agents (enrichment, crm_sync) and swaps in
Gleef-specific strategist + humanizer.

Node order:
    enrichment -> gleef_strategist -> gleef_humanizer -> crm_sync
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.agents.enrichment import run_enrichment
from app.agents.gleef_humanizer import run_gleef_humanizer
from app.agents.gleef_strategist import run_gleef_strategist
from app.agents.state import BDRState
from app.services.crm_sync import run_crm_sync

GLEEF_NODE_ORDER = ("enrichment", "gleef_strategist", "gleef_humanizer", "crm_sync")


def build_gleef_workflow():
    graph = StateGraph(BDRState)
    graph.add_node("enrichment", run_enrichment)
    graph.add_node("gleef_strategist", run_gleef_strategist)
    graph.add_node("gleef_humanizer", run_gleef_humanizer)
    graph.add_node("crm_sync", run_crm_sync)

    graph.set_entry_point("enrichment")
    graph.add_edge("enrichment", "gleef_strategist")
    graph.add_edge("gleef_strategist", "gleef_humanizer")
    graph.add_edge("gleef_humanizer", "crm_sync")
    graph.add_edge("crm_sync", END)

    return graph.compile()


_compiled = None


def get_gleef_workflow():
    global _compiled
    if _compiled is None:
        _compiled = build_gleef_workflow()
    return _compiled


def run_gleef_workflow(
    company: str,
    industry: str,
    sync_to_notion: bool = False,
) -> BDRState:
    wf = get_gleef_workflow()
    initial: BDRState = {
        "company": company,
        "industry": industry,
        "sync_to_notion": sync_to_notion,
        "agent_trace": [],
    }
    return wf.invoke(initial)
