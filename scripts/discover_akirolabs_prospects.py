"""
discover_akirolabs_prospects.py — Find large enterprises matching Akirolabs' ICP.

Akirolabs automates procurement category strategy for large enterprises.
This script asks Claude for real companies that would benefit from their product,
then writes them to pipeline/akirolabs/prospects.csv.

ICP:
  - Industries: Automotive (Tier 1), Banking/FS, Chemicals, Pharma, Energy/Utilities,
                Industrial Manufacturing
  - Size: 1,000–50,000 employees
  - Geography: Germany-headquartered OR global with strong German procurement presence
  - Persona: CPO, VP Procurement, Head of Strategic Sourcing, Head of Category Management

Reference customers: Raiffeisen Bank, Bertelsmann, Merck, Axpo

Usage:
    python scripts/discover_akirolabs_prospects.py             # write CSV
    python scripts/discover_akirolabs_prospects.py --dry-run   # print to stdout only
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
AKIROLABS_DIR = PIPELINE / "akirolabs"
PROSPECTS_CSV = AKIROLABS_DIR / "prospects.csv"

MODEL = "claude-opus-4-6"

FIELDNAMES = [
    "id",
    "company",
    "industry",
    "hq",
    "headcount",
    "spend_complexity",
    "cpo_hypothesis",
    "pain_signal",
    "linkedin_search",
    "priority",
]


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


def build_prompt() -> str:
    return """\
You are a procurement tech analyst helping identify large enterprises that are \
ideal prospects for Akirolabs — a Berlin-based AI startup that automates \
procurement category strategy for large enterprises.

AKIROLABS PRODUCT CONTEXT:
- Automates category strategy creation (market analysis, spend analysis, action plans)
- Key stat: "up to 90% faster time to strategy" vs. the traditional 6+ week PowerPoint cycle
- Pain solved: category strategy runs on PowerPoint, takes 6+ weeks, no real-time market \
signals, siloed across category managers
- Reference customers already won: Raiffeisen Bank, Bertelsmann (7 divisions), Merck, Axpo

IDEAL CUSTOMER PROFILE:
- Industries: Automotive (Tier 1 suppliers), Banking/Financial Services, Chemicals, \
Pharma/Life Sciences, Energy/Utilities, Industrial Manufacturing
- Headcount: 1,000–50,000 employees (large enough CPO function + complex indirect spend)
- Geography: Germany-headquartered OR global companies with strong German procurement \
presence (European HQ, major German operations, or German parent)
- Target personas: CPO, VP Procurement, Head of Strategic Sourcing, Head of Category Management

YOUR TASK:
Return 15–20 REAL large enterprises that clearly match this ICP. These must be companies \
you have solid, verified knowledge of — NO hallucination. If you are unsure of any detail, \
use an empty string rather than guessing.

Prioritise companies where:
  - Priority 1 (high): clearly in ICP industry + Germany-anchored + 5,000–50,000 employees \
+ obvious multi-category indirect spend pain
  - Priority 2 (medium): good ICP fit but slightly smaller / less obvious Germany connection
  - Priority 3 (lower): fits some criteria but weaker match overall

For each company provide:
  "company"           — full legal/brand name
  "industry"          — specific sub-industry (e.g. "Automotive components", \
"Specialty chemicals", "Private banking")
  "hq"                — city, country (e.g. "Munich, Germany")
  "headcount"         — approximate employee count (e.g. "~14,000" or "50,000–60,000")
  "spend_complexity"  — 1 sentence describing their indirect spend landscape \
(categories, global scope, supplier base size)
  "cpo_hypothesis"    — likely title of the procurement decision-maker at this company
  "pain_signal"       — 1 sentence: why their category strategy process is painful today \
(scale, complexity, pace of change in their supply markets)
  "linkedin_search"   — a LinkedIn boolean search string to find the CPO/Head of Procurement \
(e.g. 'CompanyName CPO OR "Head of Procurement" site:linkedin.com')
  "priority"          — integer 1, 2, or 3

IMPORTANT:
  - Return ONLY a valid JSON array. No markdown, no explanation, just the JSON.
  - Every object must have all 9 keys listed above.
  - Only include REAL companies you are confident about. No made-up or hallucinated entries.
  - Spread across multiple ICP industries — do not cluster all entries in one sector.
  - Include at least 5 German-headquartered companies and at least 3 from other European \
countries with strong German operations.

Return the JSON array now:"""


def discover(api_key: str) -> list[dict]:
    client = anthropic.Anthropic(api_key=api_key)
    print("Calling Claude (claude-opus-4-6) to identify Akirolabs prospects...")

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": build_prompt()}],
    )

    raw = resp.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        prospects = json.loads(raw)
        if not isinstance(prospects, list):
            raise ValueError(f"Expected list, got {type(prospects)}")
        print(f"Claude returned {len(prospects)} prospects.")
        return prospects
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing Claude's response: {e}", file=sys.stderr)
        # Try to find JSON array in the response
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            try:
                prospects = json.loads(raw[start : end + 1])
                print(f"Recovered {len(prospects)} prospects from partial JSON.")
                return prospects
            except json.JSONDecodeError:
                pass
        print("Could not parse response. Raw output (first 600 chars):", file=sys.stderr)
        print(raw[:600], file=sys.stderr)
        return []


def write_prospects_csv(prospects: list[dict]) -> Path:
    AKIROLABS_DIR.mkdir(parents=True, exist_ok=True)
    with PROSPECTS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for i, p in enumerate(prospects, 1):
            w.writerow({
                "id": i,
                "company": p.get("company", ""),
                "industry": p.get("industry", ""),
                "hq": p.get("hq", ""),
                "headcount": p.get("headcount", ""),
                "spend_complexity": p.get("spend_complexity", ""),
                "cpo_hypothesis": p.get("cpo_hypothesis", ""),
                "pain_signal": p.get("pain_signal", ""),
                "linkedin_search": p.get("linkedin_search", ""),
                "priority": p.get("priority", ""),
            })
    return PROSPECTS_CSV


def print_table(prospects: list[dict]) -> None:
    p1 = [p for p in prospects if str(p.get("priority", "")) == "1"]
    p2 = [p for p in prospects if str(p.get("priority", "")) == "2"]
    p3 = [p for p in prospects if str(p.get("priority", "")) == "3"]
    print(f"\n--- {len(prospects)} prospects  (p1={len(p1)}  p2={len(p2)}  p3={len(p3)}) ---\n")
    for i, p in enumerate(prospects, 1):
        print(
            f"{i:2}. [p{p.get('priority','?')}] {p.get('company','?'):35} "
            f"| {p.get('industry','?'):28} | {p.get('hq','?'):22} "
            f"| {p.get('headcount','?')}"
        )
        print(f"      {p.get('pain_signal','')[:90]}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Akirolabs ICP prospects.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print prospects to stdout, don't write CSV",
    )
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Add it to .env")

    prospects = discover(api_key)

    if not prospects:
        print("No prospects returned. Exiting.")
        return

    print_table(prospects)

    if args.dry_run:
        print("Dry run — not written to disk.")
    else:
        path = write_prospects_csv(prospects)
        print(f"Wrote {len(prospects)} prospects to {path}")
        print("\nNext steps:")
        print("  1. Review pipeline/akirolabs/prospects.csv")
        print("  2. Use linkedin_search strings to find the right contact at each company")
        print("  3. Draft personalised outreach referencing their specific pain signal")


if __name__ == "__main__":
    main()
