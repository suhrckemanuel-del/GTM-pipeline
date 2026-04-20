"""
akirolabs_bdr_v2.py — V2 dashboard for the 4-step LangGraph BDR pipeline.

Run:
    streamlit run app/akirolabs_bdr_v2.py

Three entry points:
  - Pipeline tab  : click any of the discovered prospects → runs workflow (cache-first)
  - Live Input tab: type any company name → runs the workflow
  - Settings tab  : edit the ICP tier definition + manage cached outputs

Pipeline (all in app/agents/ + app/services/):
    1. Enrichment   — Exa news + Hunter.io contacts + ICP tier
    2. Strategist   — picks 1 of 3 angles via Pydantic structured output
    3. Humanizer    — assembles DM/email via fixed string banks (anti-AI)
    4. CRM Sync     — pushes finalised prospect to Notion DB
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load secrets: st.secrets (Streamlit Cloud) takes priority, .env is local fallback
_SECRET_KEYS = (
    "ANTHROPIC_API_KEY", "EXA_API_KEY", "HUNTER_API_KEY",
    "NOTION_API_KEY", "NOTION_DATABASE_ID",
)
try:
    for _k in _SECRET_KEYS:
        if _k not in os.environ and _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

_env_path = ROOT / ".env"
if _env_path.is_file():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        if _k.strip() and _k.strip() not in os.environ:
            os.environ[_k.strip()] = _v.strip()

st.set_page_config(
    page_title="Akirolabs BDR v2 — 4-Step LangGraph",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

from app.agents.state import (  # noqa: E402
    ANGLE_DESCRIPTIONS,
    CRMSyncResult,
    EnrichmentResult,
    ProspectCard,
    StrategyDecision,
)
from app.agents.workflow_engine import (  # noqa: E402
    NODE_ORDER,
    build_workflow,
    run_workflow_stream,
)

PROSPECTS_CSV = ROOT / "pipeline" / "akirolabs" / "prospects.csv"
DISCOVER_SCRIPT = ROOT / "scripts" / "discover_akirolabs_prospects.py"
SAVED_STATES_DIR = ROOT / "pipeline" / "akirolabs" / "saved_states"
ICP_CONFIG_FILE = ROOT / "config" / "icp_definition.txt"
DISCOVERY_CONFIG_FILE = ROOT / "config" / "discovery_config.json"

_ICP_DEFAULT = (
    "You are the ICP-tier classifier for Akirolabs (a category-strategy automation "
    "platform for large enterprise procurement).\n\n"
    "Tiers:\n"
    "  - Tier 1: Strategic enterprise. Revenue >= ~€5B OR headcount >= ~50k. "
    "Multi-division or multi-country procurement organisation. Best long-term ACV.\n"
    "  - Tier 2: Mid-large. Revenue €1-5B OR headcount 10-50k. Single CPO + small team.\n"
    "  - Tier 3: Below those bands or unclear scale. Less likely fit today.\n\n"
    "Use any clues in the research summary (regions, divisions, revenue, headcount, "
    "listed status) to make your call. Be decisive — pick exactly one tier."
)


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------
def _company_slug(company: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")


def _save_state(company: str, state: dict) -> None:
    SAVED_STATES_DIR.mkdir(parents=True, exist_ok=True)
    data = {}
    for key, val in state.items():
        data[key] = val.model_dump() if hasattr(val, "model_dump") else val
    (SAVED_STATES_DIR / f"{_company_slug(company)}.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _load_state(company: str) -> dict | None:
    path = SAVED_STATES_DIR / f"{_company_slug(company)}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    _MODELS = {
        "enrichment": EnrichmentResult,
        "strategy": StrategyDecision,
        "card": ProspectCard,
        "crm_result": CRMSyncResult,
    }
    for key, cls in _MODELS.items():
        if key in data and data[key] is not None:
            try:
                data[key] = cls.model_validate(data[key])
            except Exception:
                data[key] = None
    return data


def _has_saved_state(company: str) -> bool:
    return (SAVED_STATES_DIR / f"{_company_slug(company)}.json").is_file()


def _load_icp_text() -> str:
    try:
        return ICP_CONFIG_FILE.read_text(encoding="utf-8")
    except Exception:
        return _ICP_DEFAULT


def _save_icp_text(text: str) -> None:
    ICP_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ICP_CONFIG_FILE.write_text(text, encoding="utf-8")


_DISCOVERY_CONFIG_DEFAULT = {
    "regions": ["Germany", "Austria", "Switzerland"],
    "industries": [
        "Automotive (Tier 1 suppliers)",
        "Banking/Financial Services",
        "Chemicals",
        "Pharma/Life Sciences",
        "Energy/Utilities",
        "Industrial Manufacturing",
    ],
    "headcount_min": 1000,
    "headcount_max": 50000,
}


def _load_discovery_config() -> dict:
    try:
        raw = json.loads(DISCOVERY_CONFIG_FILE.read_text(encoding="utf-8"))
        merged = dict(_DISCOVERY_CONFIG_DEFAULT)
        merged.update(raw)
        return merged
    except Exception:
        return dict(_DISCOVERY_CONFIG_DEFAULT)


def _save_discovery_config(cfg: dict) -> None:
    DISCOVERY_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    DISCOVERY_CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def _set_prospect_status(company_name: str, new_status: str) -> None:
    if not PROSPECTS_CSV.is_file():
        return
    with PROSPECTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if "status" not in fieldnames:
        fieldnames.append("status")
    for row in rows:
        if row.get("company", "").strip().lower() == company_name.strip().lower():
            row["status"] = new_status
        if not row.get("status"):
            row["status"] = "active"
    with PROSPECTS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.4rem; }
    .agent-card {
        border: 1px solid rgba(49,51,63,.15);
        border-radius: 6px;
        padding: .55rem .8rem;
        margin-bottom: .4rem;
        font-size: .9rem;
    }
    .agent-card.done    { background: #f0fff4; border-left: 4px solid #38a169; }
    .agent-card.active  { background: #fffbea; border-left: 4px solid #d69e2e; }
    .agent-card.pending { background: #f7fafc; border-left: 4px solid #cbd5e0; color: #718096; }
    .thought-line {
        font-family: ui-monospace, "SF Mono", Menlo, monospace;
        font-size: .82rem;
        color: #2d3748;
        margin: .15rem 0;
    }
    .thought-line.live { color: #b7791f; }
    .before-after-box {
        background: #f0f4ff;
        border-left: 4px solid #4361ee;
        border-radius: 4px;
        padding: .75rem 1rem;
        font-size: .92rem;
        line-height: 1.55;
    }
    .signal-pill {
        background: #f0fff4;
        border-left: 4px solid #38a169;
        border-radius: 4px;
        padding: .45rem .8rem;
        font-size: .85rem;
        margin-bottom: .35rem;
    }
    .contact-pill {
        background: #fff5f7;
        border-left: 4px solid #d53f8c;
        border-radius: 4px;
        padding: .45rem .8rem;
        font-size: .85rem;
        margin-bottom: .35rem;
    }
    .tier-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-weight: 700;
        font-size: .8rem;
        letter-spacing: .03em;
    }
    .tier-1 { background: #c6f6d5; color: #22543d; }
    .tier-2 { background: #fefcbf; color: #744210; }
    .tier-3 { background: #e2e8f0; color: #2d3748; }
    .p-badge-1 { color: #e53e3e; font-weight: 700; font-size: .85rem; }
    .p-badge-2 { color: #d69e2e; font-weight: 700; font-size: .85rem; }
    .p-badge-3 { color: #718096; font-weight: 700; font-size: .85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Akirolabs BDR v2")
st.caption("4-step LangGraph pipeline · Enrichment → Strategist → Humanizer → CRM Sync")

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
AGENTS_META = [
    ("enrichment", "Enrichment", "Exa news + Hunter.io contacts + ICP tier."),
    ("strategist",  "Strategist", "Picks 1 of 3 angles via Pydantic schema."),
    ("humanizer",   "Humanizer",  "String-concat from fixed banks (no AI voice)."),
    ("crm_sync",    "CRM Sync",   "Pushes finalised prospect into Notion DB."),
]

with st.sidebar:
    st.markdown("### 4-Step Pipeline")
    st.caption("Built by Manuel Suhrcke · April 2026")
    st.divider()
    for _key, name, desc in AGENTS_META:
        st.markdown(f"**{name}** — {desc}")
    st.divider()

    api_ok    = bool(os.environ.get("ANTHROPIC_API_KEY"))
    exa_ok    = bool(os.environ.get("EXA_API_KEY"))
    hunter_ok = bool(os.environ.get("HUNTER_API_KEY"))
    notion_ok = bool(os.environ.get("NOTION_API_KEY") and os.environ.get("NOTION_DATABASE_ID"))

    st.markdown("**Live keys**")
    st.markdown(f"- ANTHROPIC: {'✅' if api_ok else '❌'}")
    st.markdown(f"- EXA: {'✅' if exa_ok else '⚪'}")
    st.markdown(f"- HUNTER: {'✅' if hunter_ok else '⚪'}")
    st.markdown(f"- NOTION: {'✅' if notion_ok else '⚪'}")
    st.divider()
    st.caption("V1 fallback: `streamlit run app/akirolabs_bdr.py`")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
@st.cache_data
def load_prospects() -> list[dict]:
    if not PROSPECTS_CSV.is_file():
        return []
    with PROSPECTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    rows.sort(key=lambda r: (int(r.get("priority") or 9), int(r.get("id") or 0)))
    return rows


def priority_badge_html(p: str) -> str:
    cls = f"p-badge-{p}" if p in ("1", "2", "3") else "p-badge-3"
    return f'<span class="{cls}">P{p}</span>'


# ---------------------------------------------------------------------------
# Notion sync toggle (shared by Pipeline + Live Input tabs)
# ---------------------------------------------------------------------------
sync_default = notion_ok
sync_toggle = st.checkbox(
    "Sync to Notion CRM after drafting",
    value=sync_default,
    disabled=not notion_ok,
    help="Pushes the finalised prospect (strategy + email + top contact) as a new page in your Notion DB.",
)

if not api_ok:
    st.error("ANTHROPIC_API_KEY not set. Add it to `.env` and restart Streamlit.")

st.divider()

# ---------------------------------------------------------------------------
# Three-tab layout
# ---------------------------------------------------------------------------
tab_pipeline, tab_live, tab_settings = st.tabs([
    "📋 Pipeline (discovered prospects)",
    "✏️ Live Input",
    "⚙️ Settings",
])

# ---- Tab 1: Pipeline -------------------------------------------------------
with tab_pipeline:
    prospects = load_prospects()

    col_disc, col_count = st.columns([1, 3])
    with col_disc:
        discover_clicked = st.button(
            "🔍 Discover More Companies",
            help="Runs discover_akirolabs_prospects.py — calls Claude to find new ICP-fit enterprises and appends them to prospects.csv.",
            disabled=not api_ok,
        )
    with col_count:
        _active = [r for r in prospects if r.get("status", "active") == "active"]
        _arch   = [r for r in prospects if r.get("status", "active") in ("archived", "won")]
        st.caption(
            f"{len(_active)} active · {len(_arch)} archived/won · "
            f"{sum(1 for r in _active if r.get('priority') == '1')} P1 · "
            f"{sum(1 for r in _active if r.get('priority') == '2')} P2 · "
            f"{sum(1 for r in _active if r.get('priority') == '3')} P3"
        )

    if discover_clicked:
        with st.spinner("Discovering new companies via Claude + Akirolabs ICP..."):
            result = subprocess.run(
                [sys.executable, str(DISCOVER_SCRIPT)],
                capture_output=True, text=True, cwd=str(ROOT), timeout=120,
            )
        st.cache_data.clear()
        if result.returncode == 0:
            st.success("Discovery complete — pipeline refreshed.")
            st.rerun()
        else:
            st.error(f"Discovery failed:\n{result.stderr[:400] or result.stdout[:400]}")

    show_archived = st.checkbox("Show archived / won companies", value=False, key="show_archived")

    active_prospects   = [r for r in prospects if r.get("status", "active") == "active"]
    archived_prospects = [r for r in prospects if r.get("status", "active") in ("archived", "won")]
    display_prospects  = active_prospects + (archived_prospects if show_archived else [])

    if not display_prospects:
        st.info(
            "No prospects found. Click **Discover More Companies** or run "
            "`python scripts/discover_akirolabs_prospects.py` first."
        )
    else:
        st.markdown("")
        header_cols = st.columns([1, 3, 3, 2, 2])
        header_cols[0].markdown("**Pri**")
        header_cols[1].markdown("**Company**")
        header_cols[2].markdown("**Industry**")
        header_cols[3].markdown("**Actions**")
        header_cols[4].markdown("")

        for row in display_prospects:
            company_name = row.get("company", "")
            status       = row.get("status", "active")
            is_cached    = _has_saved_state(company_name)
            is_archived  = status in ("archived", "won")

            c_pri, c_company, c_industry, c_actions, c_run = st.columns([1, 3, 3, 2, 2])

            c_pri.markdown(
                priority_badge_html(row.get("priority", "3")),
                unsafe_allow_html=True,
            )

            if is_archived:
                c_company.markdown(
                    f"<span style='color:#a0aec0'>{company_name}</span>",
                    unsafe_allow_html=True,
                )
            else:
                c_company.markdown(f"**{company_name}**")

            industry_label = row.get("industry", "")
            if is_cached and not is_archived:
                industry_label += " _(cached)_"
            c_industry.caption(industry_label)

            with c_actions:
                if not is_archived:
                    col_arch, col_won = st.columns(2)
                    with col_arch:
                        if st.button(
                            "Archive",
                            key=f"arch_{row.get('id', company_name)}",
                            use_container_width=True,
                        ):
                            _set_prospect_status(company_name, "archived")
                            st.rerun()
                    with col_won:
                        if st.button(
                            "Won ✓",
                            key=f"won_{row.get('id', company_name)}",
                            use_container_width=True,
                        ):
                            _set_prospect_status(company_name, "won")
                            st.rerun()
                else:
                    badge_color = "#68d391" if status == "won" else "#a0aec0"
                    st.markdown(
                        f"<span style='color:{badge_color};font-size:.8rem;font-weight:600'>"
                        f"{status.upper()}</span>",
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "Restore",
                        key=f"restore_{row.get('id', company_name)}",
                        use_container_width=True,
                    ):
                        _set_prospect_status(company_name, "active")
                        st.rerun()

            with c_run:
                if not is_archived:
                    btn_label = "View Saved ▶" if is_cached else "Generate & Sync →"
                    if st.button(
                        btn_label,
                        key=f"run_pipeline_{row.get('id', company_name)}",
                        disabled=not api_ok and not is_cached,
                        use_container_width=True,
                    ):
                        st.session_state["_run_company"] = company_name
                        st.session_state["_run_industry"] = row.get("industry", "")
                        st.session_state["_run_triggered"] = True
                        st.session_state["_force_rerun"] = False
                        st.rerun()

# ---- Tab 2: Live Input -----------------------------------------------------
with tab_live:
    st.markdown("Enter any company to run the full pipeline in real time.")
    col1, col2 = st.columns(2)
    with col1:
        company_input = st.text_input(
            "Company", placeholder="e.g. Henkel AG", key="v2_company"
        )
    with col2:
        industry_input = st.text_input(
            "Industry", placeholder="e.g. Consumer goods / chemicals", key="v2_industry"
        )

    manual_run = st.button("Generate & Sync", type="primary", disabled=not api_ok)
    if manual_run:
        if not company_input.strip():
            st.warning("Enter a company name.")
        elif not industry_input.strip():
            st.warning("Enter an industry.")
        else:
            st.session_state["_run_company"] = company_input.strip()
            st.session_state["_run_industry"] = industry_input.strip()
            st.session_state["_run_triggered"] = True
            st.session_state["_force_rerun"] = False
            st.rerun()

# ---- Tab 3: Settings -------------------------------------------------------
with tab_settings:
    st.markdown("### ICP Definition")
    st.caption(
        "Edit the tier thresholds used by the Enrichment agent's ICP classifier. "
        "Saved changes apply immediately on the next pipeline run."
    )

    icp_text = _load_icp_text()
    edited_icp = st.text_area(
        "ICP classifier prompt",
        value=icp_text,
        height=260,
        key="icp_editor",
        help="Edit Tier 1/2/3 thresholds to adapt this pipeline to a new company's target profile.",
    )
    col_save, col_reset, _ = st.columns([1, 1, 4])
    with col_save:
        if st.button("💾 Save", type="primary", use_container_width=True):
            _save_icp_text(edited_icp)
            st.success("ICP definition saved.")
    with col_reset:
        if st.button("↺ Reset default", use_container_width=True):
            _save_icp_text(_ICP_DEFAULT)
            st.rerun()

    st.divider()
    st.markdown("### Cached Pipeline Outputs")
    st.caption(
        "Each successful pipeline run is saved to "
        "`pipeline/akirolabs/saved_states/<company_slug>.json`. "
        "Clicking a company in the Pipeline tab loads from cache automatically."
    )

    saved_files = sorted(SAVED_STATES_DIR.glob("*.json")) if SAVED_STATES_DIR.is_dir() else []
    if saved_files:
        for f in saved_files:
            col_name, col_info, col_del = st.columns([3, 2, 1])
            col_name.markdown(f"`{f.stem}`")
            try:
                col_info.caption(datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M"))
            except Exception:
                pass
            with col_del:
                if st.button("Delete", key=f"del_{f.stem}", use_container_width=True):
                    f.unlink(missing_ok=True)
                    st.success(f"Deleted {f.stem}")
                    st.rerun()
    else:
        st.info("No cached states yet. Run the pipeline on any company to save its output.")

    st.divider()
    st.markdown("### Discovery Settings")
    st.caption(
        "Configure which regions and industries Claude targets when discovering new companies. "
        "Changes apply on next **Discover More Companies** run."
    )

    disc_cfg = _load_discovery_config()

    disc_regions_raw = st.text_area(
        "Target regions (one per line or comma-separated)",
        value="\n".join(disc_cfg.get("regions", [])),
        height=100,
        key="disc_regions",
        help="Examples: Germany, UK, France, Benelux, Nordics, Southeast Asia",
    )
    disc_industries_raw = st.text_area(
        "Target industries (one per line or comma-separated)",
        value="\n".join(disc_cfg.get("industries", [])),
        height=140,
        key="disc_industries",
    )
    col_hc_min, col_hc_max = st.columns(2)
    with col_hc_min:
        disc_hc_min = st.number_input(
            "Min headcount",
            min_value=100, max_value=500000,
            value=int(disc_cfg.get("headcount_min", 1000)),
            step=500,
            key="disc_hc_min",
        )
    with col_hc_max:
        disc_hc_max = st.number_input(
            "Max headcount",
            min_value=100, max_value=500000,
            value=int(disc_cfg.get("headcount_max", 50000)),
            step=500,
            key="disc_hc_max",
        )

    def _parse_list(raw: str) -> list[str]:
        items = []
        for chunk in raw.replace(",", "\n").splitlines():
            s = chunk.strip()
            if s:
                items.append(s)
        return items

    col_disc_save, _ = st.columns([1, 3])
    with col_disc_save:
        if st.button("💾 Save Discovery Config", type="primary", use_container_width=True):
            if int(disc_hc_min) >= int(disc_hc_max):
                st.warning("Min headcount must be less than max headcount.")
            else:
                _save_discovery_config({
                    "regions":       _parse_list(disc_regions_raw),
                    "industries":    _parse_list(disc_industries_raw),
                    "headcount_min": int(disc_hc_min),
                    "headcount_max": int(disc_hc_max),
                })
                st.success("Discovery config saved — applies on next Discover More Companies run.")

    st.caption("Existing pipeline companies are always excluded from Claude's suggestions regardless of these settings.")


# ---------------------------------------------------------------------------
# Render helpers
# ---------------------------------------------------------------------------
AGENT_DISPLAY = {
    "enrichment": "Enrichment",
    "strategist": "Strategist",
    "humanizer":  "Humanizer",
    "crm_sync":   "CRM Sync",
}


def render_agent_status(active: str | None, done: set[str], skipped: set[str]) -> None:
    cols = st.columns(4, gap="small")
    for col, node in zip(cols, NODE_ORDER):
        if node in done and node not in skipped:
            cls, marker = "done", "✅"
        elif node in skipped:
            cls, marker = "done", "⏭️"
        elif node == active:
            cls, marker = "active", "⏳"
        else:
            cls, marker = "pending", "○"
        with col:
            st.markdown(
                f'<div class="agent-card {cls}">{marker} <strong>{AGENT_DISPLAY[node]}</strong></div>',
                unsafe_allow_html=True,
            )


def render_thought_log(trace: list[str]) -> None:
    if not trace:
        return
    lines = []
    for i, line in enumerate(trace):
        cls = "thought-line live" if i == len(trace) - 1 else "thought-line"
        lines.append(f'<div class="{cls}">› {line}</div>')
    st.markdown("\n".join(lines), unsafe_allow_html=True)


def split_before_after(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    if not text:
        return "", ""
    if "With Akirolabs:" in text:
        before, after = text.split("With Akirolabs:", 1)
        return before.strip(), after.strip()
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paras) >= 2:
        return paras[0], paras[1]
    return text, ""


def tier_badge(tier: int) -> str:
    return f'<span class="tier-badge tier-{tier}">Tier {tier}</span>'


def render_enrichment(enrichment) -> None:
    if not enrichment:
        return
    cols = st.columns(3)
    if enrichment.icp:
        cols[0].markdown(
            f"**ICP** · {tier_badge(enrichment.icp.tier)}",
            unsafe_allow_html=True,
        )
        cols[0].caption(enrichment.icp.rationale)
    cols[1].markdown(f"**Domain** · `{enrichment.domain or 'unknown'}`")
    cols[2].markdown(
        f"**Signals** · {len(enrichment.live_signals)} Exa · {len(enrichment.contacts)} Hunter contacts"
    )

    if enrichment.contacts:
        with st.expander(f"Hunter.io contacts ({len(enrichment.contacts)})"):
            for c in enrichment.contacts:
                line = f"<strong>{c.name or '(no name)'}</strong> — {c.position or 'unknown role'}"
                if c.email:
                    line += f" · <code>{c.email}</code>"
                if c.confidence:
                    line += f" · conf {c.confidence}"
                st.markdown(f'<div class="contact-pill">{line}</div>', unsafe_allow_html=True)

    if enrichment.live_signals:
        with st.expander(f"Exa signals ({len(enrichment.live_signals)})"):
            for s in enrichment.live_signals:
                line = f"<strong>{s.title or '(untitled)'}</strong>"
                if s.url:
                    line += f' — <a href="{s.url}" target="_blank">source</a>'
                if s.snippet:
                    line += f"<br><span style='color:#555;font-size:.85rem;'>{s.snippet[:280]}</span>"
                st.markdown(f'<div class="signal-pill">{line}</div>', unsafe_allow_html=True)

    if enrichment.research_summary:
        with st.expander("Research summary (CPO lens)"):
            st.write(enrichment.research_summary)


def render_strategy(strategy) -> None:
    if not strategy:
        return
    cols = st.columns(3)
    cols[0].markdown(f"**Persona:** {strategy.cpo_hypothesis}")
    cols[1].markdown(f"**Pain:** {strategy.pain_signal}")
    cols[2].markdown(
        f"**Recommended angle:** {strategy.angle_name} (`{strategy.recommended_angle}`)"
    )
    with st.expander("Strategist rationale"):
        st.write(strategy.rationale)


def render_card(card, strategy) -> None:
    if not card:
        return
    st.markdown("**Situation now**")
    before, after = split_before_after(card.before_after)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown(
            f'<div class="before-after-box">{before or "_(empty)_"}</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f'<div class="before-after-box"><strong>With Akirolabs:</strong> {after or "_(empty)_"}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("")
    rec_key = strategy.recommended_angle if strategy else "angle1"
    angles = list(card.angles)
    rec_idx = next((i for i, a in enumerate(angles) if a.angle_key == rec_key), 0)
    angles = angles[rec_idx:] + angles[:rec_idx]
    if rec_idx > 0:
        st.caption("Recommended angle is shown first.")

    tab_labels = [
        a.tab_label or ANGLE_DESCRIPTIONS.get(a.angle_key, {}).get("tab_label", a.angle_key)
        for a in angles
    ]
    tabs = st.tabs(tab_labels)
    for tab, angle in zip(tabs, angles):
        with tab:
            cl, cr = st.columns(2, gap="large")
            with cl:
                st.markdown("**LinkedIn DM**")
                st.text_area(
                    "dm", value=angle.dm, height=160,
                    label_visibility="collapsed", key=f"dm_{angle.angle_key}"
                )
            with cr:
                st.markdown("**Cold email**")
                if angle.email_subject:
                    st.caption(f"Subject: {angle.email_subject}")
                st.text_area(
                    "body", value=angle.email_body, height=160,
                    label_visibility="collapsed", key=f"body_{angle.angle_key}"
                )

    with st.expander("Raw JSON (guaranteed Pydantic schema output)"):
        st.json(card.model_dump())


def render_crm(result) -> None:
    if not result:
        return
    if result.skipped:
        st.info(f"CRM Sync skipped — {result.skip_reason}")
        return
    if result.success:
        msg = "✅ Pushed to Notion."
        if result.page_url:
            msg += f" [Open page]({result.page_url})"
        st.success(msg)
    else:
        st.error(f"Notion sync failed: {result.error}")


# ---------------------------------------------------------------------------
# Workflow runner — triggered by either tab via session state
# ---------------------------------------------------------------------------
if st.session_state.get("_run_triggered"):
    run_company = st.session_state.pop("_run_company", "")
    run_industry = st.session_state.pop("_run_industry", "")
    force_rerun = st.session_state.pop("_force_rerun", False)
    st.session_state["_run_triggered"] = False

    if not run_company or not run_industry:
        st.warning("Company and industry are required.")
        st.stop()

    # ---- Cache check -------------------------------------------------------
    if not force_rerun:
        cached = _load_state(run_company)
        if cached and cached.get("card"):
            st.divider()
            col_hdr, col_btn = st.columns([4, 1])
            col_hdr.success(f"Showing saved result for **{run_company}**")
            with col_btn:
                if st.button("⟳ Force Re-run", type="secondary", use_container_width=True):
                    st.session_state["_run_company"] = run_company
                    st.session_state["_run_industry"] = run_industry
                    st.session_state["_run_triggered"] = True
                    st.session_state["_force_rerun"] = True
                    st.rerun()
            st.markdown("### 1 · Enrichment")
            render_enrichment(cached.get("enrichment"))
            st.markdown("### 2 · Strategy")
            render_strategy(cached.get("strategy"))
            st.markdown("### 3 · Drafts")
            render_card(cached.get("card"), cached.get("strategy"))
            st.markdown("### 4 · CRM Sync")
            render_crm(cached.get("crm_result"))
            st.stop()

    # ---- Live run ----------------------------------------------------------
    st.divider()
    st.markdown(f"### Running pipeline for **{run_company}**")

    status_slot = st.empty()
    log_slot = st.empty()

    final_state: dict = {}
    done: set[str] = set()
    skipped: set[str] = set()
    active: str | None = "enrichment"

    with status_slot.container():
        render_agent_status(active=active, done=done, skipped=skipped)

    try:
        workflow = build_workflow()
        for _latest, state in run_workflow_stream(
            workflow,
            company=run_company,
            industry=run_industry,
            sync_to_notion=sync_toggle,
        ):
            crm_result = state.get("crm_result")
            if crm_result is not None:
                done = {"enrichment", "strategist", "humanizer", "crm_sync"}
                if crm_result.skipped:
                    skipped.add("crm_sync")
                active = None
            elif state.get("card") is not None:
                done = {"enrichment", "strategist", "humanizer"}
                active = "crm_sync"
            elif state.get("strategy") is not None:
                done = {"enrichment", "strategist"}
                active = "humanizer"
            elif state.get("enrichment") is not None:
                done = {"enrichment"}
                active = "strategist"
            else:
                done = set()
                active = "enrichment"

            final_state = state
            with status_slot.container():
                render_agent_status(active=active, done=done, skipped=skipped)
            with log_slot.container():
                render_thought_log(state.get("agent_trace", []))

            if state.get("error"):
                break
    except Exception as exc:
        st.error(f"Workflow failed: {exc}")
        st.stop()

    if final_state.get("error"):
        st.error(final_state["error"])
        st.stop()

    card = final_state.get("card")
    if not card:
        st.error("No card produced. Check the agent log above.")
        st.stop()

    # ---- Persist output ----------------------------------------------------
    _save_state(run_company, final_state)

    st.divider()
    st.success(f"Generated for **{run_company}** · output cached")

    st.markdown("### 1 · Enrichment")
    render_enrichment(final_state.get("enrichment"))

    st.markdown("### 2 · Strategy")
    render_strategy(final_state.get("strategy"))

    st.markdown("### 3 · Drafts")
    render_card(card, final_state.get("strategy"))

    st.markdown("### 4 · CRM Sync")
    render_crm(final_state.get("crm_result"))
