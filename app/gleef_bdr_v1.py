"""
gleef_bdr_v1.py — Gleef BDR Outreach Dashboard.

4-step pipeline: Enrichment -> Strategist -> Humanizer -> CRM Sync
Output: industry-grade 5-touch outreach sequence (email x3 + LinkedIn x2)
over a 15-day window, targeting VP Product / VP Engineering / Design Lead.

Gmail send: GMAIL_SENDER + GMAIL_APP_PASSWORD in .env (App Password, not OAuth).
Queue: pipeline/gleef/queued/*.json — touches 2/3/5 auto-scheduled.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Streamlit Cloud secrets -> env
_SECRET_KEYS = (
    "ANTHROPIC_API_KEY", "EXA_API_KEY", "HUNTER_API_KEY",
    "NOTION_API_KEY", "NOTION_DATABASE_ID",
    "GMAIL_SENDER", "GMAIL_APP_PASSWORD",
)
try:
    for _k in _SECRET_KEYS:
        if _k not in os.environ and _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

st.set_page_config(
    page_title="Gleef BDR — Localisation Outreach",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS — cleaner cards and header
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.4rem; font-weight: 700; }
.stExpander { border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 6px; }
div[data-testid="stHorizontalBlock"] > div { gap: 0.5rem; }
</style>
""", unsafe_allow_html=True)

PROSPECTS_CSV = ROOT / "pipeline" / "gleef" / "prospects.csv"
PRIORITY_COLOURS = {"P1": "#22c55e", "P2": "#f59e0b", "P3": "#94a3b8"}
CHANNEL_ICON = {"email": "📧", "linkedin": "💬"}
ANGLE_LABEL = {
    "angle1": "Figma-Native",
    "angle2": "Dev Experience",
    "angle3": "Brand Voice",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
@st.cache_data(ttl=120)
def load_prospects() -> list[dict]:
    if not PROSPECTS_CSV.exists():
        return []
    df = pd.read_csv(PROSPECTS_CSV, dtype=str).fillna("")
    return df.to_dict(orient="records")


def priority_badge(p: str) -> str:
    c = PRIORITY_COLOURS.get(p, "#94a3b8")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{p}</span>'


def icp_badge(tier: int) -> str:
    colours = {1: "#6366f1", 2: "#0ea5e9", 3: "#94a3b8"}
    labels = {1: "Tier 1 — Enterprise", 2: "Tier 2 — Mid-Market", 3: "Tier 3"}
    c = colours.get(tier, "#94a3b8")
    return f'<span style="background:{c};color:#fff;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:700">{labels.get(tier, f"Tier {tier}")}</span>'


def display_sequence(sequence) -> None:
    n = len(sequence.touches)
    last_day = sequence.touches[-1].day
    angle_name = ANGLE_LABEL.get(sequence.recommended_angle, sequence.recommended_angle)

    col_a, col_b, col_c = st.columns(3)
    col_a.metric("Touches", n)
    col_b.metric("Window", f"{last_day} days")
    col_c.metric("Angle", angle_name)

    st.caption(f"Target: **{sequence.entry_persona}**")
    st.divider()

    for touch in sequence.touches:
        icon = CHANNEL_ICON.get(touch.channel, "📌")
        ch_label = touch.channel.title()
        label = f"{icon} Touch {touch.touch_number} — Day {touch.day} — {ch_label}"
        if touch.subject:
            label += f"  |  {touch.subject}"

        with st.expander(label, expanded=(touch.touch_number == 1)):
            if touch.subject:
                st.caption(f"**Subject:** {touch.subject}")

            if touch.channel == "linkedin":
                st.info("LinkedIn DM — copy manually or use the clipboard button below.")
                st.code(touch.body, language=None)
                if st.button("📋 Copy LinkedIn DM", key=f"copy_li_{touch.touch_number}"):
                    st.session_state["_clipboard"] = touch.body
                    st.success("Copied to session — paste from the text area below.")
                if st.session_state.get("_clipboard") == touch.body:
                    st.text_area("LinkedIn DM (select all → copy)", touch.body, height=120,
                                 key=f"li_ta_{touch.touch_number}")
            else:
                st.code(touch.body, language=None)

            col1, col2, col3 = st.columns(3)
            col1.caption(f"~{touch.word_count} words")
            col2.caption(f"CTA: {touch.cta}")
            col3.caption(f"Day {touch.day}")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🌍 Gleef BDR")
    st.caption("AI-powered localisation outreach · 5-touch sequence")
    st.divider()

    st.markdown("**Pipeline API Keys**")
    for key in ("ANTHROPIC_API_KEY", "EXA_API_KEY", "HUNTER_API_KEY"):
        if os.environ.get(key):
            st.success(f"✓ {key.split('_')[0].title()}", icon="🔑")
        else:
            v = st.text_input(key, type="password", key=f"inp_{key}")
            if v:
                os.environ[key] = v

    st.divider()
    st.markdown("**Gmail Send**")
    for key in ("GMAIL_SENDER", "GMAIL_APP_PASSWORD"):
        if os.environ.get(key):
            st.success(f"✓ {key.replace('_', ' ').title()}", icon="📧")
        else:
            v = st.text_input(key, type="password" if "PASSWORD" in key else "default",
                              key=f"inp_{key}",
                              help="App Password from myaccount.google.com/apppasswords" if "PASSWORD" in key else "")
            if v:
                os.environ[key] = v

    st.divider()
    st.markdown("**Notion CRM (optional)**")
    sync_notion = st.toggle("Push to Notion", value=False)
    for key in ("NOTION_API_KEY", "NOTION_DATABASE_ID"):
        if sync_notion and not os.environ.get(key):
            v = st.text_input(key, type="password", key=f"inp_{key}")
            if v:
                os.environ[key] = v

    # Queue status
    st.divider()
    st.markdown("**Send Queue**")
    try:
        from app.services.gmail_sender import pending_count, get_due_touches, send_email, mark_sent
        pending = pending_count()
        due = get_due_touches()
        if pending == 0:
            st.caption("No pending touches.")
        else:
            st.metric("Pending touches", pending)
            if due:
                st.warning(f"{len(due)} touch(es) due today")
                if st.button("Send due touches now", type="primary"):
                    sent, failed = 0, 0
                    for t in due:
                        ok, err = send_email(
                            to_email=t["recipient_email"],
                            to_name=t["recipient_name"],
                            subject=t["subject"],
                            body=t["body"],
                        )
                        if ok:
                            mark_sent(t["company"], t["_source_file"].stem.split("_")[-1],
                                      t["touch_number"])
                            sent += 1
                        else:
                            st.error(f"Touch {t['touch_number']} for {t['company']}: {err}")
                            failed += 1
                    if sent:
                        st.success(f"Sent {sent} touch(es).")
    except Exception:
        st.caption("Queue unavailable.")

    st.divider()
    st.markdown("**Lead Discovery**")
    perp_key = os.environ.get("PERPLEXITY_API_KEY", "")
    if not perp_key:
        v = st.text_input("PERPLEXITY_API_KEY", type="password", key="inp_perp",
                          help="perplexity.ai/settings/api")
        if v:
            os.environ["PERPLEXITY_API_KEY"] = v
    else:
        st.success("✓ Perplexity", icon="🔍")

    st.divider()
    st.caption("Reuses: Enrichment (Exa + Hunter.io) + CRM Sync.")
    st.caption("Gleef-specific: Strategist + Humanizer + 5-touch Sequence.")


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("# 🌍 Gleef BDR — Localisation Outreach")
st.markdown(
    "5-touch outreach sequence (email × 3 + LinkedIn × 2) · "
    "VP Product / VP Engineering / Design Lead · "
    "Figma-first SaaS scaling internationally."
)
st.divider()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
tab_pipeline, tab_live, tab_queue = st.tabs([
    "📋 Prospect Pipeline", "✍️ Live Input", "📬 Send Queue"
])

# ── Pipeline tab ─────────────────────────────────────────────────────────────
with tab_pipeline:
    prospects = load_prospects()
    col_ref, col_disc, col_cnt = st.columns([1, 2, 4])
    if col_ref.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()
    if col_disc.button("🔍 Discover more", help="Uses Perplexity AI to find new Gleef leads"):
        if not os.environ.get("PERPLEXITY_API_KEY"):
            st.error("Add PERPLEXITY_API_KEY in the sidebar first.")
        else:
            with st.spinner("Asking Perplexity for new Gleef leads…"):
                try:
                    from app.services.prospect_discovery import discover_gleef_prospects
                    new, added = discover_gleef_prospects()
                    if added:
                        st.cache_data.clear()
                        st.success(f"Added {added} new prospects. Refreshing…")
                        st.rerun()
                    else:
                        st.info("No new companies found (all already in list).")
                except Exception as e:
                    st.error(f"Discovery failed: {e}")
    col_cnt.caption(f"{len(prospects)} prospects · pipeline/gleef/prospects.csv")

    if not prospects:
        st.info("Add companies to pipeline/gleef/prospects.csv")
    else:
        for row in prospects:
            c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 3, 2])
            c1.markdown(priority_badge(row.get("priority", "P2")), unsafe_allow_html=True)
            c2.markdown(f"**{row.get('company', '')}**")
            c3.caption(row.get("industry", ""))
            c4.caption(f"{row.get('hq', '')} · {row.get('notes', '')[:55]}{'…' if len(row.get('notes',''))>55 else ''}")
            if c5.button("Generate Sequence →", key=f"run_{row.get('id', row.get('company'))}"):
                st.session_state["_run_company"] = row.get("company", "")
                st.session_state["_run_industry"] = row.get("industry", "")
                st.session_state["_run_triggered"] = True
                st.rerun()

# ── Live input tab ─────────────────────────────────────────────────────────────
with tab_live:
    with st.form("live_input_form"):
        col_a, col_b = st.columns(2)
        live_company = col_a.text_input("Company name", placeholder="e.g. Personio")
        live_industry = col_b.text_input("Industry", placeholder="e.g. HR SaaS")
        if st.form_submit_button("Generate Sequence →", type="primary") and live_company.strip():
            st.session_state["_run_company"] = live_company.strip()
            st.session_state["_run_industry"] = live_industry.strip()
            st.session_state["_run_triggered"] = True
            st.rerun()

# ── Queue tab ─────────────────────────────────────────────────────────────────
with tab_queue:
    try:
        from app.services.gmail_sender import load_queue
        records = load_queue()
        if not records:
            st.info("No queued sequences yet. Generate and approve a sequence to add to queue.")
        else:
            today = date.today().isoformat()
            for rec in records:
                with st.expander(
                    f"**{rec['company']}** → {rec['recipient_email']} · created {rec['created']}",
                    expanded=False,
                ):
                    for t in rec.get("touches", []):
                        status = "✅ Sent" if t.get("sent") else (
                            "🔴 Due" if t.get("scheduled_date", "9999") <= today else
                            f"⏳ Scheduled {t.get('scheduled_date')}"
                        )
                        st.caption(
                            f"Touch {t['touch_number']} · Day {t['day']} · "
                            f"{t['channel'].title()} · {status}"
                        )
    except Exception as e:
        st.error(f"Queue load error: {e}")

# ---------------------------------------------------------------------------
# Workflow runner
# ---------------------------------------------------------------------------
if st.session_state.get("_run_triggered"):
    target_company = st.session_state.pop("_run_company", "")
    target_industry = st.session_state.pop("_run_industry", "")
    st.session_state.pop("_run_triggered", None)

    if not target_company:
        st.warning("Company name is required.")
        st.stop()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        st.error("ANTHROPIC_API_KEY is required. Set it in the sidebar.")
        st.stop()

    st.divider()
    st.markdown(f"## Sequence for **{target_company}**")

    from app.agents.gleef_workflow import run_gleef_workflow

    NODE_LABELS = {
        "enrichment":       "1 · Enrichment — Exa + Hunter.io + ICP tier",
        "gleef_strategist": "2 · Strategist — Figma-Native / Dev Experience / Brand Voice",
        "gleef_humanizer":  "3 · Humanizer — 5-touch sequence + 29-rule filter",
        "crm_sync":         "4 · CRM Sync — Notion push",
    }

    status_slots = {k: st.empty() for k in NODE_LABELS}
    for k, lbl in NODE_LABELS.items():
        status_slots[k].markdown(f"⏳ `{lbl}`")

    trace_box = st.expander("Agent thought log", expanded=False)
    final_state = None
    start = time.time()

    with st.spinner(f"Running pipeline for {target_company}…"):
        try:
            final_state = run_gleef_workflow(
                company=target_company,
                industry=target_industry,
                sync_to_notion=sync_notion,
            )
        except Exception as exc:
            st.error(f"Pipeline error: {exc}")
            st.stop()

    elapsed = time.time() - start
    for k, slot in status_slots.items():
        slot.markdown(f"✅ `{NODE_LABELS[k]}`")
    with trace_box:
        for line in (final_state or {}).get("agent_trace", []):
            st.caption(f"› {line}")

    if final_state and final_state.get("error"):
        st.error(f"Pipeline error: {final_state['error']}")
        st.stop()

    enrichment = final_state.get("enrichment") if final_state else None
    strategy   = final_state.get("strategy")   if final_state else None
    card       = final_state.get("card")       if final_state else None
    crm_result = final_state.get("crm_result") if final_state else None

    st.success(f"Pipeline complete in {elapsed:.1f}s")
    st.divider()

    # Summary metrics row
    if enrichment:
        m1, m2, m3, m4 = st.columns(4)
        icp_tier = enrichment.icp.tier if enrichment.icp else 2
        m1.markdown(f"**ICP Tier**<br>{icp_badge(icp_tier)}", unsafe_allow_html=True)
        if strategy:
            m2.markdown(f"**Angle**<br>`{ANGLE_LABEL.get(strategy.recommended_angle,'—')}`",
                        unsafe_allow_html=True)
            m3.markdown(f"**Target**<br>`{strategy.cpo_hypothesis}`", unsafe_allow_html=True)
        n_c = len(enrichment.contacts) if enrichment.contacts else 0
        m4.markdown(f"**Contacts**<br>`{n_c} via Hunter.io`", unsafe_allow_html=True)

    st.divider()

    # Results tabs
    r_seq, r_send, r_research, r_contact, r_ba, r_crm = st.tabs([
        "📍 Sequence", "📧 Send / Approve",
        "🔍 Research", "👤 Top Contact", "📝 Before/After", "🗄️ CRM"
    ])

    # ── Sequence ─────────────────────────────────────────────────────────────
    with r_seq:
        if card and card.sequence:
            display_sequence(card.sequence)
        elif card and card.angles:
            st.info("Sequence not generated — showing Touch 1 only.")
            rec_key = strategy.recommended_angle if strategy else "angle1"
            rec = next((a for a in card.angles if a.angle_key == rec_key), card.angles[0])
            st.caption(f"Subject: {rec.email_subject}")
            st.code(rec.email_body, language=None)
        else:
            st.warning("No output generated.")

    # ── Send / Approve ────────────────────────────────────────────────────────
    with r_send:
        if not card or not card.sequence:
            st.info("No sequence to send.")
        else:
            seq = card.sequence
            email_touches = [t for t in seq.touches if t.channel == "email"]
            li_touches    = [t for t in seq.touches if t.channel == "linkedin"]

            st.markdown("### Recipient")
            sc1, sc2 = st.columns(2)
            recip_email = sc1.text_input(
                "Recipient email",
                value=enrichment.contacts[0].email if (enrichment and enrichment.contacts) else "",
                key="recip_email",
            )
            recip_name = sc2.text_input(
                "Recipient name",
                value=enrichment.contacts[0].name if (enrichment and enrichment.contacts) else "",
                key="recip_name",
            )

            st.divider()
            st.markdown("### Touch 1 — Send now")
            t1 = email_touches[0] if email_touches else None
            if t1:
                t1_subj = st.text_input("Subject", value=t1.subject, key="t1_subj")
                t1_body = st.text_area("Body (editable)", value=t1.body, height=200, key="t1_body")

                gmail_ready = bool(os.environ.get("GMAIL_SENDER") and os.environ.get("GMAIL_APP_PASSWORD"))
                if not gmail_ready:
                    st.warning("Set GMAIL_SENDER and GMAIL_APP_PASSWORD in the sidebar to enable sending.")

                if st.button("✅ Approve & Send Touch 1 via Gmail", type="primary",
                             disabled=(not gmail_ready or not recip_email)):
                    from app.services.gmail_sender import send_email as _send
                    ok, err = _send(
                        to_email=recip_email,
                        to_name=recip_name,
                        subject=t1_subj,
                        body=t1_body,
                    )
                    if ok:
                        st.success(f"Touch 1 sent to {recip_email}")
                        st.session_state["_t1_sent"] = True
                    else:
                        st.error(f"Send failed: {err}")

            st.divider()
            st.markdown("### Touches 2–5 — Queue for auto-send")
            st.caption(
                "Email touches (2, 3, 5) will be scheduled and sent automatically "
                "when you click 'Send due touches' in the sidebar. "
                "LinkedIn touch (4) is manual — copy it from the Sequence tab."
            )

            future_email = [t for t in email_touches[1:]]
            if future_email:
                today = date.today()
                for t in future_email:
                    send_on = today + timedelta(days=t.day)
                    st.caption(f"Touch {t.touch_number} (Day {t.day}) → scheduled {send_on.isoformat()}")

            if li_touches:
                for t in li_touches:
                    st.caption(f"Touch {t.touch_number} (Day {t.day}) → LinkedIn · send manually")

            if st.button("📥 Queue touches 2–5 for this sequence",
                         disabled=(not recip_email or not future_email)):
                from app.services.gmail_sender import queue_sequence
                q_touches = [
                    {
                        "touch_number": t.touch_number,
                        "day": t.day,
                        "channel": t.channel,
                        "subject": t.subject,
                        "body": t.body,
                    }
                    for t in seq.touches
                    if t.touch_number > 1
                ]
                path = queue_sequence(
                    company=target_company,
                    recipient_email=recip_email,
                    recipient_name=recip_name,
                    touches=q_touches,
                )
                st.success(f"Queued {len(q_touches)} touches → {path.name}")

    # ── Research ──────────────────────────────────────────────────────────────
    with r_research:
        if enrichment:
            if enrichment.icp:
                st.markdown(f"**ICP:** {enrichment.icp.tier_label}")
                st.caption(enrichment.icp.rationale)
            if strategy:
                st.markdown(f"**Pain signal:** {strategy.pain_signal}")
                st.markdown(f"**Rationale:** {strategy.rationale}")
            st.divider()
            if enrichment.research_summary:
                st.write(enrichment.research_summary)
            if enrichment.live_signals:
                st.markdown(f"**Exa signals ({len(enrichment.live_signals)})**")
                for s in enrichment.live_signals[:5]:
                    st.markdown(f"- **{s.title}** — {s.snippet[:120]}…")
        else:
            st.warning("No enrichment data.")

    # ── Contact ───────────────────────────────────────────────────────────────
    with r_contact:
        if enrichment and enrichment.contacts:
            st.markdown(
                f"**{len(enrichment.contacts)} contacts · Hunter.io @ "
                f"{enrichment.domain or target_company}**"
            )
            for c in enrichment.contacts[:5]:
                with st.container(border=True):
                    cols = st.columns([2, 2, 2, 1])
                    cols[0].markdown(f"**{c.name or '—'}**")
                    cols[1].caption(c.position or "unknown role")
                    cols[2].caption(c.email or "no email")
                    cols[3].caption(f"{c.confidence}%")
        else:
            st.info("No contacts found. Hunter.io API key may be missing.")

    # ── Before/After ──────────────────────────────────────────────────────────
    with r_ba:
        if card:
            lines = card.before_after.split("\n\n", 1)
            st.markdown("**Before**")
            st.write(lines[0])
            if len(lines) > 1:
                st.markdown("**After**")
                st.write(lines[1])

    # ── CRM ───────────────────────────────────────────────────────────────────
    with r_crm:
        if crm_result:
            if crm_result.skipped:
                st.info(f"Notion sync skipped: {crm_result.skip_reason}")
            elif crm_result.success:
                st.success("✓ Notion page created")
                if crm_result.page_url:
                    st.markdown(f"[Open in Notion]({crm_result.page_url})")
            else:
                st.error(f"Notion sync failed: {crm_result.error}")
        else:
            st.info("CRM sync not run.")
