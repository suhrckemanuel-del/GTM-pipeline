"""
prospect_discovery.py — Perplexity-powered lead discovery for Gleef BDR.

Sends a structured prompt to the Perplexity API asking for companies that
match Gleef's ICP, then appends new results to pipeline/gleef/prospects.csv.

Perplexity uses an OpenAI-compatible endpoint — no SDK needed, just requests.
Model: llama-3.1-sonar-large-128k-online (has live web access).

Setup:
  Add to .env:  PERPLEXITY_API_KEY=pplx-...
  Get key at:   perplexity.ai/settings/api
"""
from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
GLEEF_CSV = ROOT / "pipeline" / "gleef" / "prospects.csv"

PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"
PERPLEXITY_MODEL = "llama-3.1-sonar-large-128k-online"

DISCOVERY_PROMPT = """\
Find 10 real B2B SaaS companies that are strong fits for an AI-powered UI localisation \
tool called Gleef (gleef.eu — Figma plugin + CLI for product teams).

ICP criteria — the company must match ALL of these:
1. Uses Figma for product/UI design (they have a product design team)
2. Has 50–500 employees
3. Ships software with a UI (web app, mobile app, or SaaS dashboard)
4. Operates in or is actively expanding into 2+ language markets
5. Headquartered in Europe OR is a US company with significant European operations
6. Is NOT already a known Gleef customer: Alan (health insurance, France)

Target industries: fintech, HR tech, analytics, productivity SaaS, collaboration, \
legal tech, insurtech, proptech, edtech.

For each company return a JSON object with exactly these fields:
- company: string (official company name)
- industry: string (1-4 word description)
- priority: string (P1 if 200+ employees or Series B+, else P2)
- hq: string (City, Country)
- notes: string (one sentence: why they need Gleef — be specific about their markets and Figma usage)

Return ONLY a JSON array of 10 objects. No markdown, no explanation, no preamble. \
Start with [ and end with ].
"""


def _call_perplexity(prompt: str, api_key: str) -> str:
    resp = requests.post(
        PERPLEXITY_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": PERPLEXITY_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000,
            "temperature": 0.2,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _parse_companies(raw: str) -> list[dict]:
    # Strip any markdown code fences if Perplexity wraps in ```json
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    # Find the JSON array
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON array found in Perplexity response:\n{raw[:300]}")
    return json.loads(match.group(0))


def _load_existing_names() -> set[str]:
    if not GLEEF_CSV.exists():
        return set()
    with GLEEF_CSV.open(newline="", encoding="utf-8-sig") as f:
        return {r.get("company", "").strip().lower() for r in csv.DictReader(f)}


def _next_id(existing: set[str]) -> int:
    if not GLEEF_CSV.exists():
        return 1
    with GLEEF_CSV.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    ids = []
    for r in rows:
        pid = r.get("id", "").strip().lstrip("Pp")
        if pid.isdigit():
            ids.append(int(pid))
    return (max(ids) + 1) if ids else 1


def discover_gleef_prospects(
    api_key: str = "",
    prompt: str = "",
    dry_run: bool = False,
) -> tuple[list[dict], int]:
    """
    Call Perplexity, parse results, append new companies to prospects.csv.

    Returns (new_companies_list, total_added_count).
    Skips companies already in the CSV (case-insensitive name match).
    """
    api_key = api_key or os.environ.get("PERPLEXITY_API_KEY", "").strip()
    if not api_key:
        raise ValueError("PERPLEXITY_API_KEY not set. Add it to .env or the sidebar.")

    raw = _call_perplexity(prompt or DISCOVERY_PROMPT, api_key)
    companies = _parse_companies(raw)

    existing_names = _load_existing_names()
    next_id = _next_id(existing_names)

    new_rows = []
    for c in companies:
        name = (c.get("company") or "").strip()
        if not name or name.lower() in existing_names:
            continue
        row = {
            "id": f"P{next_id:02d}",
            "company": name,
            "industry": (c.get("industry") or "").strip(),
            "priority": (c.get("priority") or "P2").strip(),
            "hq": (c.get("hq") or "").strip(),
            "notes": (c.get("notes") or "").strip(),
        }
        new_rows.append(row)
        existing_names.add(name.lower())
        next_id += 1

    if dry_run or not new_rows:
        return new_rows, 0

    GLEEF_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new_file = not GLEEF_CSV.exists()
    fieldnames = ["id", "company", "industry", "priority", "hq", "notes"]

    with GLEEF_CSV.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new_file:
            w.writeheader()
        w.writerows(new_rows)

    return new_rows, len(new_rows)
