"""
workflow_engine.py — Core orchestrator for the 4-step BDR pipeline.

    Enrichment  ->  Strategist  ->  Humanizer  ->  CRM Sync  ->  END

Each node mutates the shared BDRState. The graph is compiled once and reused
across runs. The streaming helper yields the merged state after each node so
the Streamlit dashboard can show live agent-by-agent progress.
"""
from __future__ import annotations

from typing import Generator, Tuple

from langgraph.graph import END, StateGraph

from app.agents.enrichment import run_enrichment
from app.agents.humanizer import run_humanizer
from app.agents.state import BDRState
from app.agents.strategist import run_strategist
from app.services.crm_sync import run_crm_sync


NODE_ORDER = ("enrichment", "strategist", "humanizer", "crm_sync")


def build_workflow():
    """Compile and return the LangGraph workflow."""
    graph = StateGraph(BDRState)

    graph.add_node("enrichment", run_enrichment)
    graph.add_node("strategist", run_strategist)
    graph.add_node("humanizer", run_humanizer)
    graph.add_node("crm_sync", run_crm_sync)

    graph.set_entry_point("enrichment")
    graph.add_edge("enrichment", "strategist")
    graph.add_edge("strategist", "humanizer")
    graph.add_edge("humanizer", "crm_sync")
    graph.add_edge("crm_sync", END)

    return graph.compile()


def run_workflow_stream(
    app,
    company: str,
    industry: str,
    sync_to_notion: bool = False,
) -> Generator[Tuple[str, dict], None, None]:
    """
    Stream node-by-node updates. Yields (latest_trace_line, full_state).
    """
    initial: BDRState = {
        "company": company.strip(),
        "industry": industry.strip(),
        "sync_to_notion": bool(sync_to_notion),
        "agent_trace": [],
    }
    for event in app.stream(initial, stream_mode="values"):
        trace = event.get("agent_trace", [])
        latest = trace[-1] if trace else "init"
        yield latest, event


def run_workflow(app, company: str, industry: str, sync_to_notion: bool = False) -> dict:
    """Synchronous variant — returns the final state dict."""
    initial: BDRState = {
        "company": company.strip(),
        "industry": industry.strip(),
        "sync_to_notion": bool(sync_to_notion),
        "agent_trace": [],
    }
    return app.invoke(initial)
