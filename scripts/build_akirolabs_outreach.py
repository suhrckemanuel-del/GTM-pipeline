"""
build_akirolabs_outreach.py — Generate 3 distinct outreach angle variants per company
for Akirolabs BDR demo prospects using Claude.

Reads:
  pipeline/akirolabs/prospects.csv
    columns: id, company, industry, hq, headcount, spend_complexity,
             cpo_hypothesis, pain_signal, linkedin_search, priority
  pipeline/akirolabs/outreach_angles.json
    columns: name, core_insight, opening_template, proof_point, cta, avoid

Writes:
  pipeline/akirolabs/insights.csv
    columns: id, company, industry, hq, headcount, cpo_hypothesis, pain_signal,
             before_after,
             angle1_name, angle1_dm, angle1_email_subject, angle1_email_body,
             angle2_name, angle2_dm, angle2_email_subject, angle2_email_body,
             angle3_name, angle3_dm, angle3_email_subject, angle3_email_body,
             priority

Usage:
  python scripts/build_akirolabs_outreach.py
  python scripts/build_akirolabs_outreach.py --dry-run
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

PROSPECTS_CSV      = ROOT / "pipeline" / "akirolabs" / "prospects.csv"
OUTREACH_ANGLES_JSON = ROOT / "pipeline" / "akirolabs" / "outreach_angles.json"
INSIGHTS_CSV       = ROOT / "pipeline" / "akirolabs" / "insights.csv"

MODEL = "claude-opus-4-6"


# ---------------------------------------------------------------------------
# Env helpers (reused from discover_companies.py)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_prompt(row: dict, angles: list[dict]) -> str:
    a1, a2, a3 = angles[0], angles[1], angles[2]
    return f"""You are writing outreach copy for Akirolabs — a Berlin AI startup that automates procurement category strategy for large enterprises. You are NOT a sales bot. Write like a sharp analyst who did actual research on this company.

Company: {row['company']}
Industry: {row['industry']}
HQ: {row['hq']}
Headcount: {row['headcount']}
Spend complexity: {row['spend_complexity']}
Target persona: {row['cpo_hypothesis']}
Pain signal: {row['pain_signal']}

You will generate 3 outreach angle variants. Each angle has a distinct strategic logic.

ANGLE 1 — Strategy Speed Gap
Logic: {a1['core_insight']}
Opening template: {a1['opening_template']}
Proof point to use: {a1['proof_point']}
CTA to use: {a1['cta']}
Avoid: {a1['avoid']}

ANGLE 2 — Suite Fatigue Wedge
Logic: {a2['core_insight']}
Opening template: {a2['opening_template']}
Proof point to use: {a2['proof_point']}
CTA to use: {a2['cta']}
Avoid: {a2['avoid']}

ANGLE 3 — Unmanaged Spend Trigger
Logic: {a3['core_insight']}
Opening template: {a3['opening_template']}
Proof point to use: {a3['proof_point']}
CTA to use: {a3['cta']}
Avoid: {a3['avoid']}

WRITING RULES — apply to every field:
- Direct, specific, peer-level. No sales-speak.
- No: "actually", "additionally", "testament", "landscape", "showcasing", "actively", "brutal", "transformative"
- No: "Worth a X-minute look?", "Happy to share the case", "Would love to connect"
- No rhetorical questions as openers — open with a factual observation
- No "not just X, it's Y" constructions
- Use straight quotes. Periods instead of em dashes.
- Signed "— Manuel" on DMs
- DMs: max 60 words
- Emails: 80-100 words, 3 short paragraphs (observation, proof, offer)
- Subject lines: max 8 words, specific, no "quick" or "just"

Also generate:
- before_after: 2 short paragraphs showing before/after for this specific company. Industry-specific spend categories, real pain details. Second para starts "With Akirolabs:".

Return ONLY valid JSON — no markdown fences:
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
  "angle3_email_body": "..."
}}"""


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------

def strip_fences(raw: str) -> str:
    """Strip markdown code fences if present."""
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    return raw


def call_claude(client: anthropic.Anthropic, row: dict, angles: list[dict]) -> dict | None:
    """
    Call Claude once for a single prospect row, generating all 3 angle variants.
    Returns parsed dict or None on failure.
    """
    prompt = build_prompt(row, angles)
    raw = ""
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=2400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = strip_fences(raw)

        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError(f"Expected dict, got {type(result)}")
        return result

    except json.JSONDecodeError as e:
        print(f"  Warning: JSON parse error for {row['company']}: {e}", file=sys.stderr)
        # Try to recover from partial JSON
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1:
            try:
                result = json.loads(raw[start : end + 1])
                print(f"  Recovered JSON for {row['company']}.", file=sys.stderr)
                return result
            except json.JSONDecodeError:
                pass
        print(f"  Could not parse response for {row['company']}. Skipping.", file=sys.stderr)
        return None

    except Exception as e:
        print(f"  Warning: Claude call failed for {row['company']}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def read_prospects() -> list[dict]:
    if not PROSPECTS_CSV.is_file():
        sys.exit(
            f"Error: prospects file not found at {PROSPECTS_CSV}\n"
            "Run the prospects CSV generation step first."
        )
    with PROSPECTS_CSV.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_angles() -> list[dict]:
    if not OUTREACH_ANGLES_JSON.is_file():
        sys.exit(f"Error: outreach_angles.json not found at {OUTREACH_ANGLES_JSON}")
    with OUTREACH_ANGLES_JSON.open(encoding="utf-8") as f:
        angles = json.load(f)
    if len(angles) < 3:
        sys.exit(f"Error: expected 3 angles in outreach_angles.json, got {len(angles)}")
    return angles


def write_insights_csv(enriched: list[dict], angles: list[dict]) -> None:
    INSIGHTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id", "company", "industry", "hq", "headcount",
        "cpo_hypothesis", "pain_signal",
        "before_after",
        "angle1_name", "angle1_dm", "angle1_email_subject", "angle1_email_body",
        "angle2_name", "angle2_dm", "angle2_email_subject", "angle2_email_body",
        "angle3_name", "angle3_dm", "angle3_email_subject", "angle3_email_body",
        "priority",
    ]
    with INSIGHTS_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(enriched)
    print(f"Wrote {len(enriched)} rows -> {INSIGHTS_CSV}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Akirolabs outreach with 3 angle variants per company via Claude."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print first 2 companies to stdout; do not write any files.",
    )
    args = parser.parse_args()

    load_env_file(ROOT / ".env")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Add it to .env")

    prospects = read_prospects()
    if not prospects:
        sys.exit("Error: prospects.csv is empty.")

    angles = read_angles()

    print(f"Loaded {len(prospects)} prospects from {PROSPECTS_CSV}")
    print(f"Loaded {len(angles)} outreach angles from {OUTREACH_ANGLES_JSON}")

    if args.dry_run:
        prospects = prospects[:2]
        print(f"Dry run — processing first {len(prospects)} companies only.\n")

    client = anthropic.Anthropic(api_key=api_key)

    enriched: list[dict] = []
    for i, row in enumerate(prospects, 1):
        company = row.get("company", f"row-{i}")
        total = len(prospects)
        print(f"Processing {i}/{total}: {company}...")

        result = call_claude(client, row, angles)

        enriched_row: dict = {
            "id":            row.get("id", ""),
            "company":       row.get("company", ""),
            "industry":      row.get("industry", ""),
            "hq":            row.get("hq", ""),
            "headcount":     row.get("headcount", ""),
            "cpo_hypothesis": row.get("cpo_hypothesis", ""),
            "pain_signal":   row.get("pain_signal", ""),
            "before_after":  "",
            "angle1_name":   angles[0]["name"],
            "angle1_dm":     "",
            "angle1_email_subject": "",
            "angle1_email_body":    "",
            "angle2_name":   angles[1]["name"],
            "angle2_dm":     "",
            "angle2_email_subject": "",
            "angle2_email_body":    "",
            "angle3_name":   angles[2]["name"],
            "angle3_dm":     "",
            "angle3_email_subject": "",
            "angle3_email_body":    "",
            "priority":      row.get("priority", ""),
        }

        if result:
            enriched_row["before_after"]          = result.get("before_after", "")
            enriched_row["angle1_dm"]             = result.get("angle1_dm", "")
            enriched_row["angle1_email_subject"]  = result.get("angle1_email_subject", "")
            enriched_row["angle1_email_body"]     = result.get("angle1_email_body", "")
            enriched_row["angle2_dm"]             = result.get("angle2_dm", "")
            enriched_row["angle2_email_subject"]  = result.get("angle2_email_subject", "")
            enriched_row["angle2_email_body"]     = result.get("angle2_email_body", "")
            enriched_row["angle3_dm"]             = result.get("angle3_dm", "")
            enriched_row["angle3_email_subject"]  = result.get("angle3_email_subject", "")
            enriched_row["angle3_email_body"]     = result.get("angle3_email_body", "")
        else:
            print(f"  Warning: no content generated for {company}, fields left empty.", file=sys.stderr)

        enriched.append(enriched_row)

        if args.dry_run:
            print(f"\n  --- {company} ---")
            print(f"  BEFORE/AFTER:\n  {enriched_row['before_after'][:300]}...")
            print(f"\n  ANGLE 1 DM ({angles[0]['name']}):\n  {enriched_row['angle1_dm']}")
            print(f"\n  ANGLE 2 DM ({angles[1]['name']}):\n  {enriched_row['angle2_dm']}")
            print(f"\n  ANGLE 3 DM ({angles[2]['name']}):\n  {enriched_row['angle3_dm']}")
            print()

    if args.dry_run:
        print(f"\nDry run complete — {len(enriched)} rows processed, no files written.")
        return

    write_insights_csv(enriched, angles)

    succeeded = sum(1 for r in enriched if r.get("before_after"))
    failed    = len(enriched) - succeeded
    print(f"\nDone. {succeeded}/{len(enriched)} generated successfully, {failed} failed.")
    if failed:
        print(f"  {failed} row(s) have empty content — check warnings above.")


if __name__ == "__main__":
    main()
