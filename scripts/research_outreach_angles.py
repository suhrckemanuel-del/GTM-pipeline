"""
research_outreach_angles.py — Research competitor GTM patterns via Exa, then synthesize
3 outreach angles for Akirolabs using Claude.

Output: pipeline/akirolabs/outreach_angles.json

Usage:
    python scripts/research_outreach_angles.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    import anthropic
    import exa_py
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    raise

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "pipeline" / "akirolabs" / "outreach_angles.json"

MODEL = "claude-opus-4-6"

EXA_QUERIES = [
    "\"Coupa\" OR \"Ivalua\" OR \"GEP\" OR \"Jaggaer\" outreach messaging procurement CPO enterprise 2024 2025",
    "procurement software cold email examples CPO \"category strategy\" OR \"strategic sourcing\"",
    "Akirolabs competitors \"category strategy\" enterprise procurement AI 2024 2025",
    "\"Ivalua\" OR \"GEP Smart\" case study ROI category management enterprise",
    "enterprise procurement software BDR outreach angles \"indirect spend\" OR \"category strategy\"",
]

SYNTHESIS_PROMPT = """\
You are a GTM strategist analyzing how enterprise procurement software companies approach outbound sales to CPOs and Heads of Strategic Procurement.

Here is research on how competitors (Coupa, Ivalua, GEP, Jaggaer, Zycus, SAP Ariba) market and sell:

{exa_research}

Akirolabs' differentiation:
- STRATEGY layer (category strategy refresh, AI scenario modeling, stakeholder-ready outputs) — not the execution layer
- Key stat: up to 90% faster time to strategy
- Reference customers: Bertelsmann (7 divisions), Raiffeisen Bank, Merck, Axpo
- Target persona: CPO, Head of Strategic Sourcing / Category Management
- Target companies: Large European enterprises (1,000–50,000 employees), Germany-connected

Based on this research, synthesize the 3 most effective outreach angles for Akirolabs to use with enterprise procurement leaders. For each angle:

1. Name it (short, descriptive — e.g. "Peer Reference", "Constraint", "Trigger Event")
2. Core insight: why this angle works in enterprise procurement sales (what psychological or business trigger it hits)
3. Opening line template: how to open a message with this angle (one sentence, specific, no fluff)
4. Proof point to use: which Akirolabs reference customer / stat fits this angle best
5. CTA that fits: what low-friction ask matches this angle
6. What to avoid: one thing that kills this angle if done wrong

Return ONLY valid JSON — an array of 3 objects with keys:
name, core_insight, opening_template, proof_point, cta, avoid"""


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


def run_exa_research(exa_api_key: str) -> str:
    """Run 5 Exa searches and collect titles + text snippets into a single context blob."""
    exa = exa_py.Exa(api_key=exa_api_key)
    all_snippets: list[str] = []

    for i, query in enumerate(EXA_QUERIES, 1):
        print(f"  [{i}/{len(EXA_QUERIES)}] Searching: {query[:70]}...")
        try:
            results = exa.search_and_contents(
                query,
                num_results=5,
                text={"max_characters": 500},
            )
            for r in results.results:
                title = getattr(r, "title", "") or ""
                text = getattr(r, "text", "") or ""
                url = getattr(r, "url", "") or ""
                if title or text:
                    snippet = f"[Source: {title}]\n{url}\n{text.strip()}"
                    all_snippets.append(snippet)
        except Exception as e:
            print(f"  Warning: Exa query {i} failed: {e}", file=sys.stderr)

    blob = "\n\n---\n\n".join(all_snippets)
    print(f"  Collected {len(all_snippets)} snippets from Exa.")
    return blob


def synthesize_angles(anthropic_api_key: str, exa_research: str) -> list[dict]:
    """Pass Exa research to Claude and get 3 outreach angles as structured JSON."""
    client = anthropic.Anthropic(api_key=anthropic_api_key)

    prompt = SYNTHESIS_PROMPT.format(exa_research=exa_research)

    print(f"  Calling {MODEL} for synthesis...")
    resp = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = resp.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    try:
        angles = json.loads(raw)
        if not isinstance(angles, list):
            raise ValueError(f"Expected list, got {type(angles)}")
        return angles
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  Error parsing Claude response: {e}", file=sys.stderr)
        # Recovery: find JSON array in response
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1:
            try:
                angles = json.loads(raw[start:end + 1])
                print("  Recovered angles from partial JSON.")
                return angles
            except json.JSONDecodeError:
                pass
        print("  Could not parse response. Raw output (first 800 chars):", file=sys.stderr)
        print(raw[:800], file=sys.stderr)
        return []


def print_angles(angles: list[dict]) -> None:
    """Print each angle cleanly to stdout."""
    print("\n" + "=" * 70)
    print("AKIROLABS OUTREACH ANGLES")
    print("=" * 70)
    for i, angle in enumerate(angles, 1):
        print(f"\nANGLE {i}: {angle.get('name', 'Unnamed')}")
        print("-" * 50)
        print(f"Core insight:      {angle.get('core_insight', '')}")
        print(f"Opening template:  {angle.get('opening_template', '')}")
        print(f"Proof point:       {angle.get('proof_point', '')}")
        print(f"CTA:               {angle.get('cta', '')}")
        print(f"Avoid:             {angle.get('avoid', '')}")
    print("\n" + "=" * 70)


def main() -> None:
    load_env_file(ROOT / ".env")

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not anthropic_api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set. Add it to .env")

    exa_api_key = os.environ.get("EXA_API_KEY")
    if not exa_api_key:
        sys.exit("Error: EXA_API_KEY not set. Add it to .env")

    # Step 1: Exa research
    print("\nStep 1: Running Exa competitor research...")
    exa_research = run_exa_research(exa_api_key)

    if not exa_research.strip():
        sys.exit("Error: No research collected from Exa. Check API key and network.")

    # Step 2: Claude synthesis
    print("\nStep 2: Synthesizing outreach angles with Claude...")
    angles = synthesize_angles(anthropic_api_key, exa_research)

    if not angles:
        sys.exit("Error: No angles returned from Claude synthesis.")

    # Step 3: Output
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(angles, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nWrote {len(angles)} angles to {OUTPUT_PATH}")

    print_angles(angles)


if __name__ == "__main__":
    main()
