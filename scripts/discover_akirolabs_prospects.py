"""
discover_akirolabs_prospects.py — Find large enterprises matching Akirolabs' ICP.

Akirolabs automates procurement category strategy for large enterprises.
This script asks Claude for real companies that would benefit from their product,
then APPENDS them to pipeline/akirolabs/prospects.csv (existing rows are preserved).

Target regions, industries, and headcount band are read from config/discovery_config.json
so they can be changed from the Settings tab in the dashboard without editing Python.

Reference customers: Raiffeisen Bank, Bertelsmann, Merck, Axpo

Usage:
    python scripts/discover_akirolabs_prospects.py             # append new companies
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
DISCOVERY_CONFIG = ROOT / "config" / "discovery_config.json"

MODEL = "claude-opus-4-6"

FIELDNAMES = [
    "id", "company", "industry", "hq", "headcount",
    "spend_complexity", "cpo_hypothesis", "pain_signal",
    "linkedin_search", "priority", "status",
]

DEFAULT_DISCOVERY_CONFIG = {
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


def load_discovery_config() -> dict:
    if not DISCOVERY_CONFIG.is_file():
        return dict(DEFAULT_DISCOVERY_CONFIG)
    try:
        cfg = json.loads(DISCOVERY_CONFIG.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_DISCOVERY_CONFIG)
        merged.update(cfg)
        return merged
    except Exception:
        return dict(DEFAULT_DISCOVERY_CONFIG)


def load_existing_prospects() -> tuple[list[dict], set[str], int]:
    """
    Returns (rows, excl_names, max_id).

    excl_names includes ALL companies regardless of status so Claude never
    re-suggests archived or won companies.
    """
    rows: list[dict] = []
    excl_names: set[str] = set()
    max_id = 0

    if not PROSPECTS_CSV.is_file():
        return rows, excl_names, max_id

    with PROSPECTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("status"):
                row["status"] = "active"
            rows.append(row)
            name = row.get("company", "").strip().lower()
            if name:
                excl_names.add(name)
            try:
                max_id = max(max_id, int(row.get("id") or 0))
            except ValueError:
                pass

    return rows, excl_names, max_id


def build_prompt(excl_names: set[str], cfg: dict) -> str:
    regions_str = ", ".join(cfg.get("regions", DEFAULT_DISCOVERY_CONFIG["regions"]))
    industries_str = "\n".join(
        f"    - {ind}" for ind in cfg.get("industries", DEFAULT_DISCOVERY_CONFIG["industries"])
    )
    hc_min = cfg.get("headcount_min", DEFAULT_DISCOVERY_CONFIG["headcount_min"])
    hc_max = cfg.get("headcount_max", DEFAULT_DISCOVERY_CONFIG["headcount_max"])

    excl_block = ""
    if excl_names:
        excl_block = (
            "\nCOMPANIES TO EXCLUDE (already in pipeline — do NOT suggest these):\n"
            + "\n".join(f"  - {n.title()}" for n in sorted(excl_names))
            + "\n"
        )

    return f"""\
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
- Industries:
{industries_str}
- Headcount: {hc_min:,}–{hc_max:,} employees (large enough CPO function + complex indirect spend)
- Geography: Companies headquartered in OR with strong procurement operations in: {regions_str}
- Target personas: CPO, VP Procurement, Head of Strategic Sourcing, Head of Category Management
{excl_block}
YOUR TASK:
Return 15–20 REAL large enterprises that clearly match this ICP and are NOT in the \
exclusion list above. These must be companies you have solid, verified knowledge of — \
NO hallucination. If you are unsure of any detail, use an empty string rather than guessing.

Prioritise companies where:
  - Priority 1 (high): clearly in ICP industry + in target region + 5,000–50,000 employees \
+ obvious multi-category indirect spend pain
  - Priority 2 (medium): good ICP fit but slightly smaller / less direct regional connection
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
  - Do NOT include any company from the exclusion list above.

Return the JSON array now:"""


def discover(api_key: str, excl_names: set[str], cfg: dict) -> list[dict]:
    client = anthropic.Anthropic(api_key=api_key)
    regions = ", ".join(cfg.get("regions", DEFAULT_DISCOVERY_CONFIG["regions"]))
    print(f"Calling Claude ({MODEL}) — regions: {regions}, excluding {len(excl_names)} known companies...")

    resp = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": build_prompt(excl_names, cfg)}],
    )

    raw = resp.content[0].text.strip()

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


def append_prospects_csv(
    existing_rows: list[dict],
    new_prospects: list[dict],
    max_id: int,
) -> tuple[Path, int]:
    AKIROLABS_DIR.mkdir(parents=True, exist_ok=True)
    merged = list(existing_rows)
    next_id = max_id + 1
    added = 0
    for p in new_prospects:
        row = {"id": next_id, "status": "active"}
        for k in FIELDNAMES:
            if k not in ("id", "status"):
                row[k] = p.get(k, "")
        merged.append(row)
        next_id += 1
        added += 1
    with PROSPECTS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        w.writerows(merged)
    return PROSPECTS_CSV, added


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

    cfg = load_discovery_config()
    existing_rows, excl_names, max_id = load_existing_prospects()
    print(f"Existing pipeline: {len(existing_rows)} companies. Excluding {len(excl_names)} from Claude's suggestions.")

    raw = discover(api_key, excl_names, cfg)

    if not raw:
        print("No prospects returned. Exiting.")
        return

    # Client-side dedup — safety net in case Claude ignores the exclusion list
    seen = set(excl_names)
    deduped = []
    for p in raw:
        key = p.get("company", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(p)
        else:
            print(f"  Skipping duplicate: {p.get('company')}")

    print(f"After dedup: {len(deduped)} genuinely new companies.")
    print_table(deduped)

    if args.dry_run:
        print("Dry run — not written to disk.")
    else:
        path, added = append_prospects_csv(existing_rows, deduped, max_id)
        print(f"Appended {added} new companies. Total: {len(existing_rows) + added}. Written to {path}")
        print("\nNext steps:")
        print("  1. Review pipeline/akirolabs/prospects.csv")
        print("  2. Use linkedin_search strings to find the right contact at each company")
        print("  3. Run the BDR pipeline from the dashboard on any new company")


if __name__ == "__main__":
    main()
