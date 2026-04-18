"""
akirolabs_bdr.py — Streamlit BDR demo app for Akirolabs call with Michael.

Usage:
    streamlit run app/akirolabs_bdr.py

Data:
    pipeline/akirolabs/insights.csv  (built by scripts/build_akirolabs_outreach.py)

v3 changes:
    - 3 outreach angle variants per company shown in Streamlit tabs:
        Tab 1 "Speed Gap"     — Strategy Speed Gap angle
        Tab 2 "Suite Fatigue" — Suite Fatigue Wedge angle
        Tab 3 "Spend Trigger" — Unmanaged Spend Trigger angle
    - Live generator produces all 3 angles at once.
    - render_angle_tabs() replaces render_card().
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Generator

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — MUST be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Akirolabs BDR Demo",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    /* Tighten top padding */
    .block-container { padding-top: 1.5rem; }

    /* Metric card subtle border */
    [data-testid="metric-container"] {
        border: 1px solid rgba(49, 51, 63, 0.15);
        border-radius: 8px;
        padding: 0.6rem 0.8rem;
    }

    /* Priority badge colours */
    .badge-p1 { color: #e53e3e; font-weight: 700; }
    .badge-p2 { color: #d69e2e; font-weight: 700; }
    .badge-p3 { color: #718096; font-weight: 700; }

    /* Before/After box */
    .before-after-box {
        background: #f0f4ff;
        border-left: 4px solid #4361ee;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        font-size: 0.92rem;
        line-height: 1.55;
    }

    /* Exa signal pill */
    .exa-signal {
        background: #f0fff4;
        border-left: 4px solid #38a169;
        border-radius: 4px;
        padding: 0.5rem 0.9rem;
        font-size: 0.88rem;
        margin-bottom: 0.5rem;
    }

    /* Divider spacing */
    hr { margin: 1.2rem 0; }

    /* Subtitle under main title */
    .app-subtitle {
        color: #555;
        font-size: 1.05rem;
        margin-top: -0.6rem;
        margin-bottom: 0.8rem;
    }

    /* Signal cards */
    .signal-card {
        border-left: 4px solid #e53e3e;
        background: #fff5f5;
        border-radius: 4px;
        padding: 0.6rem 1rem;
        margin-bottom: 0.5rem;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    .signal-card.urgency-2 {
        border-left-color: #d69e2e;
        background: #fffff0;
    }
    .signal-card.urgency-1 {
        border-left-color: #718096;
        background: #f7fafc;
    }
    .trigger-badge {
        background: #e53e3e;
        color: white;
        border-radius: 3px;
        padding: 1px 6px;
        font-size: 0.78rem;
        margin: 0 6px;
        text-transform: uppercase;
        letter-spacing: 0.03em;
        display: inline-block;
    }
    .angle-rec {
        color: #4361ee;
        font-weight: 600;
        margin-left: 8px;
        font-size: 0.85rem;
    }

    .summary-card {
        background: #f7fafc;
        border: 1px solid rgba(49, 51, 63, 0.12);
        border-radius: 6px;
        padding: 0.8rem 0.95rem;
        margin-bottom: 0.8rem;
        line-height: 1.45;
        font-size: 0.92rem;
    }
    .summary-label {
        display: block;
        color: #4a5568;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.02em;
        text-transform: uppercase;
        margin-bottom: 0.22rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Env loading
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]

_env_path = ROOT / ".env"
if _env_path.is_file():
    for _line in _env_path.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _, _v = _line.partition("=")
        if _k.strip() and _k.strip() not in os.environ:
            os.environ[_k.strip()] = _v.strip()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INSIGHTS_CSV = ROOT / "pipeline" / "akirolabs" / "insights.csv"
OUTREACH_ANGLES_JSON = ROOT / "pipeline" / "akirolabs" / "outreach_angles.json"
TRIGGERS_CSV = ROOT / "pipeline" / "akirolabs" / "triggers.csv"
MODEL = "claude-sonnet-4-6"

TRIGGER_LABELS = {
    "leadership_change": "New Leadership",
    "transformation": "Transformation",
    "earnings_signal": "Earnings Signal",
    "headcount_cut": "Headcount Cut",
    "peer_pressure": "Peer Pressure",
    "industry_news": "Industry News",
}

ANGLE_DESCRIPTIONS = {
    "angle1": {
        "name": "Strategy Speed Gap",
        "tab_label": "Speed Gap",
        "description": (
            "Strategy Speed Gap: the company runs category strategy refreshes on long "
            "manual cycles. Akirolabs cuts that cycle by up to 90%. Focus the DM and "
            "email on the time cost of the current process and the speed gain."
        ),
    },
    "angle2": {
        "name": "Suite Fatigue Wedge",
        "tab_label": "Suite Fatigue",
        "description": (
            "Suite Fatigue Wedge: the procurement team pays for a large ERP or "
            "spend-analytics suite that still can't automate category strategy narrative "
            "and stakeholder presentations. Akirolabs fills that gap without replacing "
            "their existing stack. Focus on the gap the incumbent suite leaves open."
        ),
    },
    "angle3": {
        "name": "Unmanaged Spend Trigger",
        "tab_label": "Spend Trigger",
        "description": (
            "Unmanaged Spend Trigger: a specific tail-spend or indirect category is "
            "growing without a documented strategy. Akirolabs lets one analyst build a "
            "defensible category strategy in days, not months. Focus on the unmanaged "
            "spend risk and the analyst bandwidth constraint."
        ),
    },
}

MOJIBAKE_REPLACEMENTS = {
    "â€”": "-",
    "â€“": "-",
    "â€˜": "'",
    "â€™": "'",
    'â€œ': '"',
    'â€\x9d': '"',
    "Â·": "·",
    "Ã¼": "u",
    "Ã¶": "o",
    "Ã¤": "a",
    "ÃŸ": "ss",
}

GENERATE_SYSTEM = """\
You are a B2B sales research assistant helping Akirolabs — a Berlin AI startup \
that automates procurement category strategy for large enterprises (CPOs, Heads of \
Strategic Sourcing). Akirolabs cuts category strategy cycle time by up to 90% vs. \
the traditional 6-week PowerPoint cycle. Reference customers: Raiffeisen Bank, \
Bertelsmann (7 divisions), Merck, Axpo.

WRITING RULES — apply to all copy you generate:
- Write like a smart analyst, not a sales bot. Direct, specific, peer-level.
- No AI vocabulary: never use "actually", "additionally", "testament", "landscape", \
"showcasing", "actively", "brutal", "transformative", "leverage" as a verb.
- No formulaic CTAs: never "Worth a X-minute look?", "Happy to share the case", \
"Would love to connect". End with a plain, specific offer.
- No rhetorical questions as openers. Open with a factual observation.
- No "not just X, it's Y" constructions. State points directly.
- Vary sentence structure. Don't repeat the same pattern across fields.
- Use straight quotes only. No em dashes — use commas or periods instead."""

GENERATE_USER_TEMPLATE = """\
Generate a BDR research card for a prospect company that Akirolabs could target.

Company: {company}
Industry: {industry}
{exa_block}
You must produce THREE distinct outreach angles. Each angle has its own LinkedIn DM \
and cold email. Use these full angle definitions:

{angle_blocks}

For each angle write:
  - A LinkedIn DM (max 60 words, signed "— Manuel"). Open with a factual observation \
specific to {company}'s spend or category challenge. Reference Bertelsmann (7 divisions, \
up to 90% faster) where it fits the angle. End with one specific, plain offer (not a \
question). No "brutal", no "worth a X-minute look", no "happy to share".
  - An email subject line (max 8 words, specific to {company}'s category or spend area, \
not a question, no "quick" or "just").
  - A cold email body (80-100 words, 3 short paragraphs). Para 1: one-sentence \
observation about {company}'s specific procurement challenge (name a real spend \
category). Para 2: what Bertelsmann achieved with Akirolabs across 7 divisions (up \
to 90% faster strategy refresh). Para 3: plain offer to share a 10-minute demo or the \
Bertelsmann case. Sign off "Manuel Suhrcke". No fluff, no "I hope this finds you well", \
no "transformative".

Also produce:
  "before_after" — 2 short paragraphs. First paragraph: how {company}'s procurement \
team currently runs category strategy refresh — specific to their scale, spend \
categories, and industry dynamics. Show the pain concretely: time, manual steps, data \
silos. Second paragraph (starting "With Akirolabs:"): what changes — akiroAssist \
synthesises market intelligence, auto-populates risk/SWOT frameworks, models scenarios, \
generates stakeholder-ready summaries. Use Akirolabs' stat: up to 90% faster.

  "cpo_hypothesis" — likely title of the procurement decision-maker \
(e.g. "Chief Procurement Officer")
  "pain_signal" — one sentence: the specific category strategy pain at this company today

Return a JSON object with exactly these keys (no extras, no markdown fences):

{{
  "before_after": "...",
  "angle1_dm": "...",
  "angle1_email_subject": "...",
  "angle1_email_body": "...",
  "angle2_dm": "...",
  "angle2_email_subject": "...",
  "angle2_email_body": "...",
  "angle3_dm": "...",
  "angle3_email_subject": "...",
  "angle3_email_body": "...",
  "cpo_hypothesis": "...",
  "pain_signal": "..."
}}

Return ONLY valid JSON. No markdown fences, no explanation."""

EXA_QUERY_TEMPLATE = (
    "{company} procurement strategy OR supply chain OR sourcing news"
)


def clean_text(text: str) -> str:
    cleaned = text or ""
    for bad, good in MOJIBAKE_REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = cleaned.replace("akirolabs", "Akirolabs")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r" ?\n ?", "\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


@st.cache_data
def load_angle_definitions() -> list[dict]:
    if not OUTREACH_ANGLES_JSON.is_file():
        return []
    with OUTREACH_ANGLES_JSON.open(encoding="utf-8") as f:
        return json.load(f)[:3]


def build_angle_prompt_block(angles: list[dict]) -> str:
    if len(angles) < 3:
        return "\n\n".join(
            [
                f"ANGLE 1 - {ANGLE_DESCRIPTIONS['angle1']['name']}\n{ANGLE_DESCRIPTIONS['angle1']['description']}",
                f"ANGLE 2 - {ANGLE_DESCRIPTIONS['angle2']['name']}\n{ANGLE_DESCRIPTIONS['angle2']['description']}",
                f"ANGLE 3 - {ANGLE_DESCRIPTIONS['angle3']['name']}\n{ANGLE_DESCRIPTIONS['angle3']['description']}",
            ]
        )

    angle_keys = ["angle1", "angle2", "angle3"]
    blocks: list[str] = []
    for idx, angle in enumerate(angles[:3]):
        meta = ANGLE_DESCRIPTIONS[angle_keys[idx]]
        blocks.append(
            "\n".join(
                [
                    f"ANGLE {idx + 1} - {meta['name']}",
                    f"Core logic: {clean_text(angle.get('core_insight', ''))}",
                    f"Opening pattern: {clean_text(angle.get('opening_template', ''))}",
                    f"Proof point: {clean_text(angle.get('proof_point', ''))}",
                    f"Offer style: {clean_text(angle.get('cta', ''))}",
                    f"Avoid: {clean_text(angle.get('avoid', ''))}",
                ]
            )
        )
    return "\n\n".join(blocks)

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
@st.cache_data
def load_insights() -> list[dict]:
    if not INSIGHTS_CSV.is_file():
        return []
    with INSIGHTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key, value in row.items():
            row[key] = clean_text(value)
    rows.sort(key=lambda r: (int(r.get("priority") or 9), int(r.get("id") or 0)))
    return rows


@st.cache_data(ttl=300)
def load_triggers() -> dict[str, dict]:
    """Returns dict keyed by company name -> trigger row. Only non-none triggers."""
    if not TRIGGERS_CSV.is_file():
        return {}
    with TRIGGERS_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key, value in row.items():
            row[key] = clean_text(value)
    return {
        r["company"]: r
        for r in rows
        if r.get("trigger_type", "none") not in ("none", "")
    }


# ---------------------------------------------------------------------------
# Exa live signal
# ---------------------------------------------------------------------------
def fetch_exa_signal(company: str, api_key: str) -> str | None:
    """Return a one-sentence live web signal for *company*, or None on failure."""
    if not api_key:
        return None
    try:
        from exa_py import Exa  # type: ignore
    except ImportError:
        return None
    try:
        exa = Exa(api_key=api_key)
        results = exa.search(
            EXA_QUERY_TEMPLATE.format(company=company),
            num_results=3,
            use_autoprompt=True,
        )
        if not results.results:
            return None
        top = results.results[0]
        title = (top.title or "").strip()
        url = (top.url or "").strip()
        if title:
            return f"{title} - {url}" if url else title
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Claude streaming call
# ---------------------------------------------------------------------------
def _stream_prospect_card(
    company: str, industry: str, api_key: str, exa_signal: str | None
) -> Generator[str, None, None]:
    """
    Yield text chunks from Claude via the streaming API.
    The full accumulated text is expected to be valid JSON when done.
    """
    try:
        import anthropic
    except ImportError:
        yield "__ERROR__: anthropic package not installed."
        return

    exa_block = ""
    if exa_signal:
        exa_block = (
            f"\nRecent signal about this company (from live web search):\n"
            f"  {exa_signal}\n"
            f"Incorporate this context where relevant.\n"
        )

    prompt = GENERATE_USER_TEMPLATE.format(
        company=company.strip(),
        industry=industry.strip(),
        exa_block=exa_block,
        angle_blocks=build_angle_prompt_block(load_angle_definitions()),
    )

    client = anthropic.Anthropic(api_key=api_key)

    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=GENERATE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text


def _parse_card_json(raw: str) -> dict | None:
    """Parse the JSON card from a raw Claude response string."""
    text = raw.strip()
    # Strip markdown fences if present
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return None


def generate_prospect_card(
    company: str, industry: str, api_key: str, exa_signal: str | None
) -> dict | None:
    """Stream Claude's response silently, then return the parsed JSON dict."""
    collected: list[str] = []
    status = st.empty()
    status.markdown("*Generating with Claude...*")

    try:
        for chunk in _stream_prospect_card(company, industry, api_key, exa_signal):
            if chunk.startswith("__ERROR__:"):
                status.empty()
                st.error(chunk[len("__ERROR__:"):].strip())
                return None
            collected.append(chunk)
    except Exception as exc:
        status.empty()
        st.error(f"Claude generation failed: {clean_text(str(exc))}")
        return None

    status.empty()
    raw = clean_text("".join(collected))
    result = _parse_card_json(raw)
    if result is None:
        st.error(f"Could not parse Claude response as JSON.\n\nRaw:\n\n{raw[:400]}")
    return result


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
def priority_badge(p: str) -> str:
    badges = {"1": "P1", "2": "P2", "3": "P3"}
    return badges.get(str(p), f"P{p}")


def split_before_after(before_after: str) -> tuple[str, str]:
    text = clean_text(before_after)
    if not text:
        return "", ""
    if "With Akirolabs:" in text:
        before, after = text.split("With Akirolabs:", 1)
        return before.strip(), after.strip()
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 2:
        return paragraphs[0], paragraphs[1]
    return text, ""


def angle_proof(angle_key: str) -> str:
    proofs = {
        "angle1": "Bertelsmann, 7 divisions, up to 90% faster strategy refresh.",
        "angle2": "Merck and Axpo, strategy layer on top of the existing stack.",
        "angle3": "Raiffeisen Bank, more categories under formal strategy without more headcount.",
    }
    return proofs.get(angle_key, "")


def build_talk_track(row: dict, angle_key: str) -> str:
    company = row.get("company", "")
    if angle_key == "angle2":
        return f"{company} already has execution tooling, the gap is the strategy layer before sourcing starts."
    if angle_key == "angle3":
        return f"{company} is a coverage conversation, how much indirect spend still runs without a current strategy."
    return f"{company} is a timing conversation, category strategy has to move faster than the business is changing."


def render_account_summary(row: dict, trigger: dict, recommended_angle: str) -> None:
    why_now = trigger.get("trigger_summary") or row.get("pain_signal", "")
    best_angle = ANGLE_DESCRIPTIONS.get(recommended_angle, {}).get("name") or "Review all 3 angles"
    proof = angle_proof(recommended_angle or "angle1")
    talk_track = build_talk_track(row, recommended_angle or "angle1")

    cols = st.columns(4, gap="small")
    items = [
        ("Why now", why_now),
        ("Best angle", best_angle),
        ("Proof", proof),
        ("Talk track", talk_track),
    ]
    for col, (label, value) in zip(cols, items):
        with col:
            st.markdown(
                (
                    '<div class="summary-card">'
                    f'<span class="summary-label">{label}</span>'
                    f"{clean_text(value) or '-'}"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )


def render_angle_tabs(
    row_id: str,
    before_after: str,
    angle_data_list: list[dict],
    recommended_angle: str = "",
) -> None:
    """
    Render:
      1. Before/After (full-width, blue left-border div)
      2. Three tabs — one per angle — each with two columns:
           Left:  LinkedIn DM in st.text_area
           Right: Email subject (caption) + body in st.text_area

    Parameters
    ----------
    row_id : str
        Unique identifier for this row (used in widget keys).
    before_after : str
        HTML/markdown text for the Before/After block.
    angle_data_list : list of dict, length 3
        Each dict has keys: name, tab_label, dm, email_subject, email_body.
    recommended_angle : str
        If set (e.g. "angle1"), rotate tabs so the recommended angle appears first.
    """
    before_text, after_text = split_before_after(before_after)
    st.markdown("**Situation now**")
    col_before, col_after = st.columns(2, gap="large")
    with col_before:
        if before_text:
            st.markdown(
                f'<div class="before-after-box">{before_text}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("_No insight available._")
    with col_after:
        if after_text:
            st.markdown(
                f'<div class="before-after-box"><strong>With Akirolabs:</strong> {after_text}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("_No projected state available._")

    st.markdown("")

    PLACEHOLDER = "Run build_akirolabs_outreach.py to populate."

    # Rotate angle_data_list so recommended appears first
    if recommended_angle and recommended_angle in ("angle1", "angle2", "angle3"):
        idx_map = {"angle1": 0, "angle2": 1, "angle3": 2}
        rec_idx = idx_map.get(recommended_angle, 0)
        angle_data_list = angle_data_list[rec_idx:] + angle_data_list[:rec_idx]
        st.caption("Recommended angle is shown first.")

    tab_labels = [a["tab_label"] for a in angle_data_list]
    tabs = st.tabs(tab_labels)

    for angle_num, (tab, angle) in enumerate(zip(tabs, angle_data_list), start=1):
        with tab:
            dm_val = angle.get("dm", "").strip()
            subj_val = angle.get("email_subject", "").strip()
            body_val = angle.get("email_body", "").strip()

            missing = not dm_val and not subj_val and not body_val

            col_li, col_email = st.columns(2, gap="large")

            with col_li:
                st.markdown("**LinkedIn DM**")
                st.text_area(
                    label="linkedin_dm",
                    value=dm_val if not missing else PLACEHOLDER,
                    height=140,
                    label_visibility="collapsed",
                    key=f"dm_{row_id}_{angle_num}",
                    disabled=missing,
                )

            with col_email:
                st.markdown("**Cold email**")
                if subj_val:
                    st.caption(f"Subject: {subj_val}")
                st.text_area(
                    label="email_body",
                    value=body_val if not missing else PLACEHOLDER,
                    height=140,
                    label_visibility="collapsed",
                    key=f"em_{row_id}_{angle_num}",
                    disabled=missing,
                )


def render_exa_signal(signal: str) -> None:
    st.markdown(
        f'<div class="exa-signal"><strong>Live signal:</strong> {clean_text(signal)}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar(rows: list[dict], n_triggers: int = 0, n_urgent: int = 0) -> list[dict]:
    """Render sidebar controls and return the filtered row list."""
    with st.sidebar:
        st.markdown("### Akirolabs BDR Demo")
        st.caption(
            "Built by Manuel Suhrcke · GTM intern candidate · April 2026"
        )
        st.divider()

        # --- Priority filter ---
        st.markdown("**Filter by priority**")
        p_options = ["All", "P1 only", "P2 only", "P3 only"]
        priority_filter = st.radio(
            "Priority", p_options, index=0, label_visibility="collapsed"
        )

        st.divider()

        # --- Headcount filter ---
        st.markdown("**Filter by size**")
        size_options = {
            "All sizes": None,
            "< 15 000": 15_000,
            "< 50 000": 50_000,
            ">= 50 000": -1,  # sentinel for large
        }
        size_choice = st.selectbox(
            "Company size", list(size_options.keys()), label_visibility="collapsed"
        )
        size_threshold = size_options[size_choice]

        st.divider()

        # --- Quick-jump company list ---
        st.markdown("**Companies in pipeline**")
        for r in rows:
            badge = priority_badge(r.get("priority", ""))
            st.markdown(
                f"{badge} {r.get('company', '')}",
                help=r.get("industry", ""),
            )

        st.divider()
        st.markdown("**Signal scan**")
        st.metric("Active triggers", n_triggers)
        if n_urgent:
            st.caption(f"{n_urgent} high urgency")
        st.divider()
        st.caption(f"Model: `{MODEL}`")
        st.caption("Powered by Anthropic Claude + Exa")

    # Apply filters
    filtered = rows
    if priority_filter != "All":
        p_val = priority_filter[1]  # "1", "2", or "3"
        filtered = [r for r in filtered if str(r.get("priority", "")) == p_val]

    if size_threshold is not None:
        size_filtered = []
        for r in filtered:
            hc_raw = r.get("headcount", "")
            nums = re.findall(r"[\d,]+", hc_raw.replace(" ", ""))
            if not nums:
                size_filtered.append(r)
                continue
            hc_max = max(int(n.replace(",", "")) for n in nums)
            if size_threshold == -1:
                if hc_max >= 50_000:
                    size_filtered.append(r)
            else:
                if hc_max < size_threshold:
                    size_filtered.append(r)
        filtered = size_filtered

    return filtered


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Akirolabs BDR Pipeline")
st.markdown(
    '<p class="app-subtitle">18 large enterprises &nbsp;|&nbsp; '
    "CPO / Head of Strategic Procurement &nbsp;|&nbsp; Germany-connected</p>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
all_rows = load_insights()

if not all_rows:
    st.warning(
        "No data found. Run `python scripts/build_akirolabs_outreach.py` to generate "
        "`pipeline/akirolabs/insights.csv`, then refresh this page."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Load triggers
# ---------------------------------------------------------------------------
triggers = load_triggers()
n_urgent = sum(1 for t in triggers.values() if str(t.get("urgency", "0")) == "3")

# ---------------------------------------------------------------------------
# Sidebar (returns filtered list)
# ---------------------------------------------------------------------------
rows = render_sidebar(all_rows, n_triggers=len(triggers), n_urgent=n_urgent)

# ---------------------------------------------------------------------------
# Summary stats (based on filtered set)
# ---------------------------------------------------------------------------
p1_count = sum(1 for r in rows if str(r.get("priority")) == "1")
p2_count = sum(1 for r in rows if str(r.get("priority")) == "2")
p3_count = sum(1 for r in rows if str(r.get("priority")) == "3")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Showing", len(rows), delta=f"{len(all_rows)} total")
m2.metric("Priority 1", p1_count)
m3.metric("Priority 2", p2_count)
m4.metric("Priority 3", p3_count)

st.divider()

# Guard: nothing to show after filtering
if not rows:
    st.info("No prospects match the current filter. Adjust filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# Live signals
# ---------------------------------------------------------------------------
st.subheader("Live signals")

col_refresh, col_ts = st.columns([1, 3])
with col_refresh:
    if st.button("Refresh Signals", type="secondary"):
        with st.spinner("Fetching live signals via Exa..."):
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "fetch_triggers.py")],
                capture_output=True,
                text=True,
                cwd=str(ROOT),
                timeout=300,
            )
        st.cache_data.clear()
        if result.returncode == 0:
            st.success("Signals refreshed.")
        else:
            st.error(f"Fetch failed: {result.stderr[:300]}")
        st.rerun()
with col_ts:
    if triggers:
        sample = next(iter(triggers.values()))
        ts = sample.get("fetched_at", "")
        if ts:
            st.caption(f"Last fetched: {ts[:16].replace('T', ' ')} UTC")

# Show top signal cards (urgency >= 2, max 5)
high_triggers = sorted(
    [t for t in triggers.values() if int(t.get("urgency", 0)) >= 2],
    key=lambda t: -int(t.get("urgency", 0))
)[:5]

if not TRIGGERS_CSV.is_file():
    st.info("No signals loaded. Click Refresh Signals to scan all 18 companies via Exa.")
elif not triggers:
    st.info("No active triggers found in last scan.")
else:
    for t in high_triggers:
        urgency = str(t.get("urgency", "1"))
        company_name = t.get("company", "")
        ttype = t.get("trigger_type", "")
        label = TRIGGER_LABELS.get(ttype, ttype)
        summary = clean_text(t.get("trigger_summary", ""))
        rec = t.get("recommended_angle", "")
        rec_name = ANGLE_DESCRIPTIONS.get(rec, {}).get("name", "")
        angle_span = f'<span class="angle-rec">\u2192 {rec_name}</span>' if rec_name else ""
        st.markdown(
            f'<div class="signal-card urgency-{urgency}">'
            f'<strong>{company_name}</strong>'
            f'<span class="trigger-badge">{label}</span>'
            f'{summary}{angle_span}'
            f'</div>',
            unsafe_allow_html=True,
        )
    if len([t for t in triggers.values() if int(t.get("urgency", 0)) >= 2]) > 5:
        remaining = len([t for t in triggers.values() if int(t.get("urgency", 0)) >= 2]) - 5
        st.caption(f"...and {remaining} more, see company cards below.")

st.divider()

# ---------------------------------------------------------------------------
# Prospect table (compact overview)
# ---------------------------------------------------------------------------
st.subheader("Pipeline at a glance")

table_md = "| # | Company | Industry | HQ | Headcount | Persona | Best angle | Priority | Signal |\n"
table_md += "|---|---------|----------|----|-----------|---------|------------|----------|--------|\n"
for r in rows:
    industry_short = r.get("industry", "")
    if len(industry_short) > 35:
        industry_short = industry_short[:32].rstrip() + "..."
    sig = triggers.get(r.get("company", ""), {})
    best_angle = ANGLE_DESCRIPTIONS.get(sig.get("recommended_angle", ""), {}).get("tab_label", "-")
    urg = str(sig.get("urgency", "0"))
    tlabel = TRIGGER_LABELS.get(sig.get("trigger_type", ""), "")
    if tlabel and urg == "3":
        sig_col = f"\U0001f534 {tlabel}"
    elif tlabel and urg == "2":
        sig_col = f"\U0001f7e1 {tlabel}"
    elif tlabel:
        sig_col = f"\u26aa {tlabel}"
    else:
        sig_col = "\u2014"
    table_md += (
        f"| {r.get('id', '')} "
        f"| **{r.get('company', '')}** "
        f"| {industry_short} "
        f"| {r.get('hq', '')} "
        f"| {r.get('headcount', '')} "
        f"| {r.get('cpo_hypothesis', '')} "
        f"| {best_angle} "
        f"| {priority_badge(r.get('priority', ''))} "
        f"| {sig_col} |\n"
    )
st.markdown(table_md)

st.divider()

# ---------------------------------------------------------------------------
# Expandable per-company cards
# ---------------------------------------------------------------------------
st.subheader("Company deep-dives")

for r in rows:
    row_id = str(r.get("id", ""))
    label = (
        f"{priority_badge(r.get('priority', ''))}  "
        f"**{r.get('company', '')}** - {r.get('industry', '')} ({r.get('hq', '')})"
    )
    with st.expander(label):
        pain = r.get("pain_signal", "")
        if pain:
            st.markdown(f"*{pain}*")
            st.markdown("")

        trigger = triggers.get(r.get("company", ""), {})
        recommended_angle = trigger.get("recommended_angle", "")
        render_account_summary(r, trigger, recommended_angle)
        if trigger:
            trigger_label = TRIGGER_LABELS.get(trigger.get("trigger_type", ""), "Signal")
            summary = trigger.get("trigger_summary", "")
            message = f"**{trigger_label}:** {summary}" if summary else f"**{trigger_label}**"
            if recommended_angle in ANGLE_DESCRIPTIONS:
                message += f" Lead with **{ANGLE_DESCRIPTIONS[recommended_angle]['name']}**."
            st.info(message)

        # Build the 3-angle list from CSV columns
        angle_data_list = [
            {
                "name": ANGLE_DESCRIPTIONS["angle1"]["name"],
                "tab_label": ANGLE_DESCRIPTIONS["angle1"]["tab_label"],
                "dm": r.get("angle1_dm", ""),
                "email_subject": r.get("angle1_email_subject", ""),
                "email_body": r.get("angle1_email_body", ""),
            },
            {
                "name": ANGLE_DESCRIPTIONS["angle2"]["name"],
                "tab_label": ANGLE_DESCRIPTIONS["angle2"]["tab_label"],
                "dm": r.get("angle2_dm", ""),
                "email_subject": r.get("angle2_email_subject", ""),
                "email_body": r.get("angle2_email_body", ""),
            },
            {
                "name": ANGLE_DESCRIPTIONS["angle3"]["name"],
                "tab_label": ANGLE_DESCRIPTIONS["angle3"]["tab_label"],
                "dm": r.get("angle3_dm", ""),
                "email_subject": r.get("angle3_email_subject", ""),
                "email_body": r.get("angle3_email_body", ""),
            },
        ]

        render_angle_tabs(
            row_id,
            r.get("before_after", ""),
            angle_data_list,
            recommended_angle=recommended_angle,
        )

st.divider()

# ---------------------------------------------------------------------------
# Live generator — streaming + Exa signals, all 3 angles at once
# ---------------------------------------------------------------------------
st.subheader("Live generator - add a prospect mid-call")
st.markdown(
    "Michael suggests a company -> fetch a live Exa signal -> stream Claude's "
    "before/after + all 3 outreach angles in real time."
)

api_key = os.environ.get("ANTHROPIC_API_KEY", "")
exa_api_key = os.environ.get("EXA_API_KEY", "")

col_keys1, col_keys2 = st.columns(2)
with col_keys1:
    if not api_key:
        st.error("ANTHROPIC_API_KEY not set. Add it to your `.env` file.")
with col_keys2:
    if not exa_api_key:
        st.caption("💡 Set EXA_API_KEY in `.env` to enable live web signals.")

company_input = st.text_input(
    "Company name", placeholder="e.g. Henkel AG", key="gen_company"
)
industry_input = st.text_input(
    "Industry", placeholder="e.g. Consumer goods / chemicals", key="gen_industry"
)

use_exa = st.checkbox(
    "Fetch live Exa signal before generating",
    value=bool(exa_api_key),
    disabled=not exa_api_key,
    help="Uses Exa web search to surface a recent news/signal for the company.",
)

if st.button("Generate", type="primary", disabled=not api_key):
    if not company_input.strip():
        st.warning("Enter a company name first.")
    elif not industry_input.strip():
        st.warning("Enter an industry first.")
    else:
        # Step 1 - optional Exa signal
        exa_signal: str | None = None
        if use_exa and exa_api_key:
            with st.spinner(f"Fetching live signal for {company_input.strip()} via Exa..."):
                exa_signal = fetch_exa_signal(company_input.strip(), exa_api_key)
            if exa_signal:
                render_exa_signal(exa_signal)
            else:
                st.caption("No Exa signal found, proceeding without live context.")

        # Step 2 - streaming Claude call (all 3 angles)
        st.markdown(
            f"Streaming Claude response for **{company_input.strip()}**..."
        )
        result = generate_prospect_card(
            company_input, industry_input, api_key, exa_signal
        )

        if result:
            st.success(f"Generated for **{company_input.strip()}**")

            pain = result.get("pain_signal", "")
            persona = result.get("cpo_hypothesis", "")
            if pain or persona:
                col_a, col_b = st.columns(2)
                if persona:
                    col_a.markdown(f"**Target persona:** {persona}")
                if pain:
                    col_b.markdown(f"*{pain}*")
                st.markdown("")

            live_angle_data = [
                {
                    "name": ANGLE_DESCRIPTIONS["angle1"]["name"],
                    "tab_label": ANGLE_DESCRIPTIONS["angle1"]["tab_label"],
                    "dm": result.get("angle1_dm", ""),
                    "email_subject": result.get("angle1_email_subject", ""),
                    "email_body": result.get("angle1_email_body", ""),
                },
                {
                    "name": ANGLE_DESCRIPTIONS["angle2"]["name"],
                    "tab_label": ANGLE_DESCRIPTIONS["angle2"]["tab_label"],
                    "dm": result.get("angle2_dm", ""),
                    "email_subject": result.get("angle2_email_subject", ""),
                    "email_body": result.get("angle2_email_body", ""),
                },
                {
                    "name": ANGLE_DESCRIPTIONS["angle3"]["name"],
                    "tab_label": ANGLE_DESCRIPTIONS["angle3"]["tab_label"],
                    "dm": result.get("angle3_dm", ""),
                    "email_subject": result.get("angle3_email_subject", ""),
                    "email_body": result.get("angle3_email_body", ""),
                },
            ]

            render_angle_tabs("live", result.get("before_after", ""), live_angle_data)
