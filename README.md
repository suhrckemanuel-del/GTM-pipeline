# AI-Powered BDR Pipeline

An agentic BDR pipeline scoped to **Gleef's ICP** — turns a company name into a full 3-touch outreach sequence with self-critique evaluation, signal-weighted scoring, and Notion CRM sync.

Built to be a portfolio-grade proof of work: shows both engineering depth (LangGraph, agentic loops, structured output) and GTM competency (ICP scoring, sequence logic, signal prioritisation).

---

## Getting started on a new machine

```bash
git clone https://github.com/<your-username>/GTM-internship-outreach.git
cd GTM-internship-outreach

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# open .env and fill in all five keys (see Keys section below)

streamlit run app/akirolabs_bdr_v2.py
# opens at http://localhost:8501
```

That's it — no database setup, no Docker, no other config needed.

---

## API keys needed

Open `.env` and fill in:

| Key | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API keys |
| `EXA_API_KEY` | exa.ai → Dashboard → API |
| `HUNTER_API_KEY` | hunter.io → Dashboard → API |
| `NOTION_API_KEY` | notion.so/my-integrations → New integration |
| `NOTION_DATABASE_ID` | Open your Notion DB → copy the hex ID from the URL |
| `GMAIL_APP_PASSWORD` | myaccount.google.com/apppasswords (needs 2FA enabled) |

---

## Current state (what works today)

4-step LangGraph pipeline running in a Streamlit UI:

```
Company name
    │
    ▼
1. Enrichment   — Exa news signals + Hunter.io contacts + Claude ICP tier (1/2/3)
    │
    ▼
2. Strategist   — picks 1 of 3 outreach angles (Pydantic structured output)
    │
    ▼
3. Humanizer    — assembles DM/email from fixed string banks (anti-AI pattern)
    │
    ▼
4. CRM Sync     — pushes finalised prospect to Notion DB
```

Key files:
- `app/akirolabs_bdr_v2.py` — Streamlit UI (Pipeline / Live Input / Settings tabs)
- `app/agents/enrichment.py` — Step 1: Exa + Hunter + ICP tier
- `app/agents/strategist.py` — Step 2: angle selection
- `app/agents/humanizer.py` — Step 3: copy assembly
- `app/agents/workflow_engine.py` — LangGraph graph definition
- `app/agents/state.py` — shared `BDRState` dataclass
- `pipeline/akirolabs/prospects.csv` — pre-seeded prospect list
- `config/icp_definition.txt` — ICP tier criteria (editable in Settings tab)

---

## Build plan — industry-grade version

This is the north star. Each item below is a discrete build task.

### 1. Gleef ICP config (`config/gleef_icp.json`)
Replace the generic `icp_definition.txt` with a structured JSON that encodes:
- Who Gleef sells to (e-commerce brands, SaaS with localisation needs, Shopify merchants)
- Key pain points Gleef solves (conversion drop-off on localised pages, slow A/B test cycles)
- Proof points / social proof to weave into outreach
- Competitor names to avoid mentioning
- Tone guidelines (Gleef is Paris-based, design-led — copy should reflect that)

All agents read from this config so the whole pipeline is Gleef-specific by default.

### 2. Signal-weighted ICP scoring (`app/agents/scorer.py`)
Replace the 3-tier classification with a **0–100 composite score**. Weighted signals:
- Recent funding round (+30)
- Hiring SDR / BDR / Growth roles (+20) — signals they're investing in outbound
- Recent product launch or press mention (+15)
- Headcount in Gleef's sweet spot range (+20)
- Geographic fit (EU-first for Gleef) (+15)

Output: `icp_score: int`, `score_breakdown: dict`, `priority: high/medium/low`.
This replaces the vague tier with something a real sales team would use.

### 3. Full 3-touch sequence generation (`app/agents/sequencer.py`)
Replace single-email output with a **complete sequence** generated in one run:
- Touch 1 — direct value insight (what you see, why now)
- Touch 2 — add proof / case study / alternative angle (5 days later)
- Touch 3 — breakup email, low-friction ask (7 days after touch 2)

Each touch is a separate structured output with `subject`, `body`, `send_delay_days`, `channel` (email or LinkedIn DM).

### 4. Self-critique evaluation loop (`app/agents/evaluator.py`)
After the sequencer, an evaluation agent scores each draft on:
- Personalisation (does it reference a real signal about this company?)
- Relevance (does it map to Gleef's actual ICP pain points?)
- CTA clarity (is there one clear ask?)
- AI-pattern score (does it sound human?)

Scoring via a second Claude call (LLM-as-judge). If any dimension scores below 7/10, the evaluator returns revision notes and the sequencer rewrites. Loop max 2 iterations.

This is the most technically impressive piece — a real agentic reflection loop.

### 5. SQLite persistence (`app/db/pipeline.py`)
Replace CSV state with a local SQLite database:
- `prospects` table — company, domain, icp_score, signals, status
- `sequences` table — 3 touches per prospect, send status, timestamps
- `runs` table — full pipeline run log with inputs, outputs, eval scores

Benefits: resumable runs, pipeline history, query the data, no CSV drift.

### 6. Updated Streamlit UI (`app/akirolabs_bdr_v2.py`)
- Pipeline tab shows icp_score (0–100) instead of tier
- Sequence tab shows all 3 touches per prospect with send status
- Eval tab shows score breakdown per draft (personalisation / relevance / CTA / human-ness)
- Settings tab loads/saves `config/gleef_icp.json`

---

## Suggested build order

1. `config/gleef_icp.json` — no code, just research; defines everything else
2. `app/agents/scorer.py` — swap out ICP tier, test it on 5 known companies
3. `app/agents/sequencer.py` — extend humanizer to 3 touches
4. `app/agents/evaluator.py` — the evaluation loop (most impressive, build this fourth)
5. `app/db/pipeline.py` — SQLite backend (can do last, CSV works fine until then)
6. UI updates — wire everything together in Streamlit

---

## CV bullet (target)

> Built a production agentic BDR pipeline (LangGraph, Claude API) with self-critique evaluation loops, signal-weighted ICP scoring, and full 3-touch sequence generation — scoped to Gleef's ICP and deployed as a Streamlit app.
