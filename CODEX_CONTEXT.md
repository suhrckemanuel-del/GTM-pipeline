# Codex Context — Akirolabs BDR Demo

## What this is

A live BDR research and outreach demo built for a Monday (2026-04-20) exploratory call with Michael at Akirolabs (Head of Sales, ex-Roland Berger, ex-KPMG). The demo answers the question: "Could this person build and run BDR for us?"

The deliverable is a Streamlit app (`app/akirolabs_bdr.py`) running at localhost:8501 that shows:
- 18 pre-researched prospect companies (Akirolabs' ICP — large EU enterprises with complex procurement)
- 3 distinct outreach angle variants per company (LinkedIn DM + email for each)
- A live generator that takes any company name + industry and produces all 3 angles via Claude in real time

The call framing: "I ran the same outreach system I built for my own job search — retargeted it at your ICP. Here's what came out." Then open the app.

---

## Owner

Manuel Suhrcke — GTM intern candidate, suhrckemanuel@gmail.com

---

## Tech stack

- **Python 3.14** (Windows)
- **Streamlit** — app UI
- **Anthropic SDK** (`anthropic`) — Claude claude-sonnet-4-6 for live generation, claude-opus-4-6 for batch scripts
- **Exa** (`exa_py`) — live web signal fetch before Claude calls
- **Hunter.io** — email enrichment (used in main outreach pipeline, not in Akirolabs demo)
- **CSV + json** — no database, no ORM

All API keys are in `.env` at project root. Already loaded by env-loading block in every script.

---

## File structure (Akirolabs demo only)

```
app/
  akirolabs_bdr.py              # Streamlit demo app — MAIN DELIVERABLE

scripts/
  discover_akirolabs_prospects.py   # Step 1: Claude generates 18 ICP companies
  research_outreach_angles.py       # Step 2: Exa + Claude synthesises 3 outreach angles
  build_akirolabs_outreach.py       # Step 3: Claude generates 3 angle variants per company
  rewrite_akirolabs_dms.py          # One-off: humanized the original DMs (already run)

pipeline/akirolabs/
  prospects.csv                 # 18 companies (input to build script)
  outreach_angles.json          # 3 angle definitions (input to build script)
  insights.csv                  # 18 companies × 3 angles (output — app reads this)

outreach/akirolabs/
  notion_page.md                # Notion-ready export of pipeline
  prospects_summary.md          # Quick reference table
```

---

## Data pipeline

```
discover_akirolabs_prospects.py
  └─ Claude (opus-4-6) → pipeline/akirolabs/prospects.csv (18 companies)

research_outreach_angles.py
  └─ Exa (5 competitor searches) + Claude (opus-4-6) → pipeline/akirolabs/outreach_angles.json

build_akirolabs_outreach.py
  └─ reads prospects.csv + outreach_angles.json
  └─ Claude (opus-4-6), 1 call per company → pipeline/akirolabs/insights.csv (18 rows × 21 cols)

app/akirolabs_bdr.py
  └─ reads insights.csv
  └─ live generator: Exa signal + Claude (sonnet-4-6) streaming → 3 angle variants on the fly
```

---

## insights.csv schema (21 columns)

```
id, company, industry, hq, headcount, cpo_hypothesis, pain_signal, before_after,
angle1_name, angle1_dm, angle1_email_subject, angle1_email_body,
angle2_name, angle2_dm, angle2_email_subject, angle2_email_body,
angle3_name, angle3_dm, angle3_email_subject, angle3_email_body,
priority
```

---

## The 3 outreach angles

Synthesised from competitor research (Coupa, Ivalua, GEP, Jaggaer, Zycus) via Exa + Claude. Full definitions in `pipeline/akirolabs/outreach_angles.json`.

### Angle 1 — Strategy Speed Gap (`angle1_*`)
**Core logic:** Category strategy refresh takes 6–8 weeks on PowerPoint/Excel. CPOs are under pressure to be strategic, not just operational. Akirolabs cuts that cycle by up to 90%.
**Proof point:** Bertelsmann — 7 divisions, up to 90% faster time to strategy.
**Avoid:** Any AI/platform/feature framing. Anchor to the strategic output, not the technology.

### Angle 2 — Suite Fatigue Wedge (`angle2_*`)
**Core logic:** The CPO paid millions for Coupa/Ariba/GEP for execution (POs, sourcing events, invoices) but strategy still lives in PowerPoint before anything hits the system. Akirolabs is the strategy layer ON TOP of the existing stack — not a replacement.
**Proof point:** Merck + Axpo using Akirolabs alongside existing procurement stack.
**Avoid:** Never imply their S2P investment was wrong. Validate it, then fill the gap above it.

### Angle 3 — Unmanaged Spend Trigger (`angle3_*`)
**Core logic:** 15–40% of indirect spend runs outside any formal category strategy. CFOs ask CPOs about it. CPOs can't scale headcount to cover it. Lead with the diagnostic ("how many categories have a current strategy?") not the product.
**Proof point:** Raiffeisen Bank International — brought autopilot categories under formal strategy using Akirolabs.
**Avoid:** Do NOT make this a cost savings pitch. Keep it a strategic coverage / governance maturity conversation.

---

## App structure (`app/akirolabs_bdr.py`)

```
set_page_config (wide layout, sidebar expanded)
Custom CSS block
Env loading
Constants (INSIGHTS_CSV, MODEL, ANGLE_DESCRIPTIONS, GENERATE_SYSTEM, GENERATE_USER_TEMPLATE)
load_insights() — @st.cache_data, sorts by priority then id
fetch_exa_signal() — exa_py, degrades gracefully if not installed or key missing
_stream_prospect_card() — generator, yields text chunks from client.messages.stream()
_parse_card_json() — JSON fence stripping + regex fallback
generate_prospect_card() — runs streaming silently, returns parsed dict
priority_badge() — returns emoji badge string
render_angle_tabs(row_id, before_after, angle_data_list) — MAIN RENDER FUNCTION
  └─ shows before/after (blue left-border div)
  └─ st.tabs with 3 tabs: "Speed Gap" | "Suite Fatigue" | "Spend Trigger"
  └─ each tab: 2 columns — LinkedIn DM (text_area) | Email subject + body (text_area)
  └─ keys: f"dm_{row_id}_{angle_num}" and f"em_{row_id}_{angle_num}"
render_exa_signal() — green left-border pill
render_sidebar(rows) — sidebar with filters, quick-nav, pipeline steps, returns filtered rows

Main flow:
  title + subtitle ("18 large enterprises | CPO / Head of Strategic Procurement | Germany-connected")
  load data → render_sidebar → summary metrics → guard if empty
  "Pipeline at a glance" markdown table
  "Company deep-dives" — 18 expanders, each calls render_angle_tabs()
  "Live generator" section — Exa checkbox + company/industry inputs + Generate button
    → fetch_exa_signal → generate_prospect_card (streaming) → render_angle_tabs("live", ...)
```

---

## Known issues / optimization tasks for Codex

### 1. Humanization — HIGHEST PRIORITY
The email bodies in `insights.csv` still contain AI patterns that slipped through:
- "Worth your time?" appears in some Angle 1 email closers — should be a plain statement offer
- Some emails open with "I" — should open with an observation about the company
- Repetitive paragraph structure across companies in the same angle
- Run the humanizer pass on all 54 email bodies (18 companies × 3 angles) and the 54 DMs

The 29 humanizer rules are:
- No "actually", "additionally", "testament", "landscape", "showcasing", "actively", "brutal", "transformative"
- No "Worth a X-minute look?", "Happy to share the case", "Would love to connect"
- No rhetorical openers — start with a factual observation
- No em dashes — use commas or periods
- No "not just X, it's Y"
- CTAs must be plain offers, not questions
- Open emails with company-specific observation, not "I"
- Max 60 words for DMs, 80-100 words for emails

### 2. Sidebar logo — broken external URL
`render_sidebar()` loads the Akirolabs logo from a hardcoded external URL that may not resolve. Replace with either:
- Remove the `st.image()` call entirely (cleanest for a demo)
- Or use a text header instead

### 3. Live generator — prompt completeness
`GENERATE_USER_TEMPLATE` in the app describes the 3 angles briefly. The build script uses the full angle JSON (core_insight, opening_template, proof_point, cta, avoid). The live generator prompt should be updated to use the full angle definitions from `outreach_angles.json` for consistency.

### 4. Streaming UX
Currently streams silently with a "Generating with Claude..." text placeholder. Could show a subtle progress indicator. Not critical.

### 5. Table verbosity
The "Pipeline at a glance" markdown table has full industry names like "Automotive components / Industrial bearings" which overflow cells. Truncate industry to 35 chars in the table row.

### 6. Before/after content — encoding artefacts
Some before/after text may contain `â€"` or `â` characters (UTF-8/Windows-1252 mojibake from em dashes). Strip these in the `load_insights()` function or during CSV write.

### 7. Error handling in live generator
If `_stream_prospect_card()` raises an `anthropic.APIError`, it currently propagates uncaught. Wrap in try/except in `generate_prospect_card()` and show `st.error()` with the message.

### 8. `rewrite_akirolabs_dms.py` — cleanup
This was a one-off script. Can be deleted or moved to `scripts/archive/`.

---

## Run instructions

```bash
# From project root
python scripts/discover_akirolabs_prospects.py       # regenerate prospects (optional)
python scripts/research_outreach_angles.py           # regenerate angles (optional)
python scripts/build_akirolabs_outreach.py           # regenerate insights.csv
python -m streamlit run app/akirolabs_bdr.py         # launch demo app
```

All scripts support `--dry-run` flag.

---

## What Michael will evaluate on the call

1. Did Manuel understand our ICP? (large EU enterprises, CPO/procurement persona)
2. Did he do real research or just run a generic prompt? (company-specific pain signals)
3. Can the system generate new content live, mid-call? (live generator moment)
4. Does the outreach copy sound like a human wrote it? (humanization quality)
5. Does he understand our positioning? (strategy layer, not S2P execution suite)

The 3-angle structure matters because Michael will naturally want to say "try it on this company." The live generator handles that. The 3 tabs let him say "for this account I'd lead with Suite Fatigue" — showing Manuel understands account-level angle selection.
