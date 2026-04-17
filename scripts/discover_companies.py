"""
discover_companies.py — Find new fast-growing startup candidates using Claude's knowledge.

Claude's training cutoff (Aug 2025) covers the 2024-2025 funding cycle perfectly.
The script asks Claude for real, verifiable startups matching the same profile as the
existing pipeline, then deduplicates and writes to CSV.

Criteria:
  - Headcount ≤ 80
  - Seed or Series A (Series B only if very fast-growing + small team)
  - Funded 2024–2025
  - 50% EU / 50% US
  - Verticals: AI agents, AI infra, AI PLG, AI security, embedded fintech, B2B payments

Output:
  pipeline/new_companies_candidates.csv (same schema as companies.csv, IDs start at next available)

Usage:
    python scripts/discover_companies.py             # write CSV
    python scripts/discover_companies.py --dry-run   # print to stdout only
    python scripts/discover_companies.py --n 30      # target 30 candidates
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = ROOT / "pipeline"
COMPANIES_CSV = PIPELINE / "companies.csv"
CANDIDATES_CSV = PIPELINE / "new_companies_candidates.csv"

MODEL = "claude-sonnet-4-6"


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def load_existing() -> tuple[set[str], int, list[dict]]:
    """Return (existing names set, max id, full rows list)."""
    names: set[str] = set()
    max_id = 40
    rows: list[dict] = []
    if not COMPANIES_CSV.is_file():
        return names, max_id, rows
    with COMPANIES_CSV.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            names.add(row["name"].strip().lower())
            rows.append(row)
            try:
                max_id = max(max_id, int(row["company_id"]))
            except ValueError:
                pass
    return names, max_id, rows


def build_prompt(existing_rows: list[dict], n_target: int) -> str:
    # Summarise the existing pipeline so Claude knows the benchmark quality
    existing_summary = "\n".join(
        f"  - {r['name']} ({r['vertical']}, {r['geography']}, {r['stage']}, "
        f"{r['headcount_estimate']} people) — {r['must_haves_notes']}"
        for r in existing_rows
        if r.get("priority", "3") in ("1", "2")
    )

    return f"""You are a GTM research analyst helping a student build a cold outreach pipeline to fast-growing startups.

Here are the EXISTING companies in the pipeline (priority 1 & 2 only, to set the quality bar):
{existing_summary}

YOUR TASK: Identify {n_target} NEW startup candidates NOT already in that list, matching:
  - Headcount ≤ 80 at time of funding (early-stage, founder-accessible)
  - Stage: Pre-Seed, Seed, or Series A (Series B only if team is still very small and fast-growing)
  - Funded in 2024 or 2025
  - Geography split: ~50% EU (France, Germany, UK, Netherlands, Spain, Sweden, Switzerland, etc.)
              and ~50% US
  - Verticals (pick from):
      AI: agents/copilots for enterprise, developer infra (compute, orchestration, vector DB, memory),
          workflow automation, PLG tools (code/content/product), LLM security/governance, applied ML
      Fintech: embedded payments, B2B payments, working capital/revenue infra, FX/cross-border, billing for AI

QUALITY BAR:
  - Real companies you have solid knowledge of (not hallucinated)
  - Clear, specific GTM opportunity or challenge (like the must_haves_notes above)
  - Fast-growing signal: recent funding round, press coverage, hiring surge
  - Founder/GTM lead should be reachable (not a mega-corp)

IMPORTANT:
  - DO NOT include any company already in the existing list above
  - DO NOT hallucinate — only include real companies you have solid knowledge of
  - If unsure about a detail, use an empty string rather than guessing

Return ONLY a valid JSON array. No markdown, no explanation, just the JSON.
Each object must have these exact keys:
  "name"                  — company name
  "domain"                — website domain, e.g. "company.ai" (empty string if unsure)
  "vertical"              — "AI" or "Fintech"
  "geography"             — e.g. "EU-France", "EU-Germany", "EU-UK", "US", "US-NYC", "US-SF"
  "stage"                 — "Pre-Seed", "Seed", "Series A", or "Series B"
  "headcount_estimate"    — e.g. "15-30", "30-60" (empty string if unsure)
  "recent_growth_signals" — 1-2 sentences: funding amount, round date, press signal
  "hiring_signals"        — what they're hiring for (empty string if unsure)
  "must_haves_notes"      — specific GTM opportunity or challenge (be concrete, like examples above)
  "priority"              — 1=high (clear GTM need + tiny team + warm signal), 2=medium, 3=lower

Return the JSON array now:"""


def discover(n_target: int, api_key: str, existing_rows: list[dict]) -> list[dict]:
    client = anthropic.Anthropic(api_key=api_key)
    print(f"Asking Claude for {n_target} candidates...")

    resp = client.messages.create(
        model=MODEL,
        max_tokens=6000,
        messages=[{"role": "user", "content": build_prompt(existing_rows, n_target)}],
    )

    raw = resp.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        candidates = json.loads(raw)
        if not isinstance(candidates, list):
            raise ValueError(f"Expected list, got {type(candidates)}")
        print(f"Claude returned {len(candidates)} candidates.")
        return candidates
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing Claude's response: {e}", file=sys.stderr)
        # Try to find JSON array in the response
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            try:
                candidates = json.loads(raw[start : end + 1])
                print(f"Recovered {len(candidates)} candidates from partial JSON.")
                return candidates
            except json.JSONDecodeError:
                pass
        print("Could not parse response. Raw output (first 600 chars):", file=sys.stderr)
        print(raw[:600], file=sys.stderr)
        return []


def run_discovery(n_target: int) -> tuple[list[dict], int]:
    load_env_file(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Add it to .env")

    existing_names, max_id, existing_rows = load_existing()
    print(f"Existing pipeline: {len(existing_names)} companies. Next ID will be {max_id + 1}.")

    # Ask for slightly more than needed to allow for dedup losses
    candidates = discover(n_target + 5, api_key, existing_rows)

    # Deduplicate against existing pipeline
    seen: set[str] = set(existing_names)
    deduped = []
    for c in candidates:
        key = c.get("name", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(c)
        elif key in existing_names:
            print(f"  Skipping duplicate (already in pipeline): {c.get('name')}")

    print(f"After dedup: {len(deduped)} new candidates.")
    return deduped, max_id


def write_candidates_csv(candidates: list[dict], start_id: int) -> Path:
    fieldnames = [
        "company_id", "name", "vertical", "geography", "stage",
        "headcount_estimate", "recent_growth_signals", "hiring_signals",
        "checklist_pass", "must_haves_notes", "priority", "notes",
    ]
    with CANDIDATES_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for i, c in enumerate(candidates):
            w.writerow({
                "company_id": start_id + 1 + i,
                "name": c.get("name", ""),
                "vertical": c.get("vertical", ""),
                "geography": c.get("geography", ""),
                "stage": c.get("stage", ""),
                "headcount_estimate": c.get("headcount_estimate", ""),
                "recent_growth_signals": c.get("recent_growth_signals", ""),
                "hiring_signals": c.get("hiring_signals", ""),
                "checklist_pass": "TBD",
                "must_haves_notes": c.get("must_haves_notes", ""),
                "priority": c.get("priority", "TBD"),
                "notes": f"domain:{c.get('domain', '')}",
            })
    return CANDIDATES_CSV


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover new startup candidates.")
    parser.add_argument("--dry-run", action="store_true", help="Print candidates, don't write CSV")
    parser.add_argument("--n", type=int, default=20, help="Target number of candidates (default 20)")
    args = parser.parse_args()

    candidates, max_id = run_discovery(n_target=args.n)

    if not candidates:
        print("No candidates found.")
        return

    eu = [c for c in candidates if c.get("geography", "").startswith("EU")]
    us = [c for c in candidates if c.get("geography", "").startswith("US")]

    if args.dry_run:
        print(f"\n--- {len(candidates)} candidates ({len(eu)} EU / {len(us)} US) ---\n")
        for i, c in enumerate(candidates, 1):
            print(
                f"{i:2}. [{c.get('geography','?'):12}] {c.get('name','?'):30} "
                f"({c.get('stage','?')}, ~{c.get('headcount_estimate','?'):8}ppl) "
                f"p{c.get('priority','?')}  {c.get('must_haves_notes','')[:70]}"
            )
        print(f"\nDry run complete — not saved. Run without --dry-run to write CSV.")
    else:
        path = write_candidates_csv(candidates, max_id)
        print(f"\nWrote {len(candidates)} candidates to {path} ({len(eu)} EU, {len(us)} US)")
        print("\nNext steps:")
        print("  1. Open pipeline/new_companies_candidates.csv and delete any rows that don't fit")
        print("  2. python scripts/build_companies.py --append pipeline/new_companies_candidates.csv")
        print("  3. Follow normal pipeline: build_contacts_outreach.py -> value-notes -> emails")


if __name__ == "__main__":
    main()
