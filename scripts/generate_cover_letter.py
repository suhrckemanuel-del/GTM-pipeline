"""
generate_cover_letter.py

Generate a humanized cover letter / motivation answer for a startup job application.

Usage:
  python scripts/generate_cover_letter.py --jd path/to/jd.txt --question "Why us?"
  python scripts/generate_cover_letter.py --jd path/to/jd.txt --question-file q.txt --dry-run --verbose
  python scripts/generate_cover_letter.py --jd path/to/jd.txt --question "..." --company "Adaptive ML"
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
POSITIONING_DIR = ROOT / "positioning"
OUTPUT_DIR = ROOT / "outreach" / "cover-letters"
ENV_FILE = ROOT / ".env"

MODEL = "claude-sonnet-4-6"
MIN_WORDS = 200
MAX_WORDS = 350

# ---------------------------------------------------------------------------
# .env loader (same pattern as enrich_emails.py)
# ---------------------------------------------------------------------------

def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


# ---------------------------------------------------------------------------
# Positioning loader
# ---------------------------------------------------------------------------

def load_positioning() -> dict:
    bios_path = POSITIONING_DIR / "one-liner-and-bios.md"
    offers_path = POSITIONING_DIR / "internship-offers.md"

    if not bios_path.is_file():
        sys.exit(f"Missing positioning file: {bios_path}")
    if not offers_path.is_file():
        sys.exit(f"Missing positioning file: {offers_path}")

    return {
        "bios_raw": bios_path.read_text(encoding="utf-8"),
        "offers_raw": offers_path.read_text(encoding="utf-8"),
    }


# ---------------------------------------------------------------------------
# Slug helper
# ---------------------------------------------------------------------------

def slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


# ---------------------------------------------------------------------------
# System prompt (cached across all three Claude calls)
# ---------------------------------------------------------------------------

def build_system_prompt(positioning: dict) -> str:
    bios = positioning["bios_raw"]
    offers = positioning["offers_raw"]

    return f"""You are a specialist cover letter writer for Manuel Suhrcke, an economics student \
applying for GTM internships at early-stage startups. Your outputs must be 200–350 words, written \
in first person, in Manuel's voice.

## Manuel's positioning context

{bios}

## Internship formats Manuel offers

{offers}

## Humanizer rules — non-negotiable output constraints

Apply ALL of the following. Violations will be caught in a dedicated audit pass.

BANNED WORDS — remove or rewrite the sentence entirely:
- "actually" (as filler)
- "additionally"
- "testament"
- "landscape" (used as a metaphor, e.g. "competitive landscape")
- "showcasing"
- "actively" (as filler, e.g. "I am actively looking")
- "serves as" → rewrite using "is"
- "boasts" → rewrite using "has"
- "features" when it means "has" or "includes"
- "At its core" → delete the phrase
- "Let's dive in" → delete
- "Here's what you need to know" → delete
- "could potentially" → "may"
- "in order to" → "to"
- "not just X, it's Y" or "not only X but also Y" → state both points directly without the construction

STRUCTURAL CONSTRAINTS:
- Maximum ONE em dash (—) in the entire letter. Use commas or periods instead of additional em dashes.
- No bold formatting (**text** or *text*) anywhere in the final output.
- No bullet points. Prose only.
- No generic startup enthusiasm ("I love building things," "I am passionate about innovation").
- No hedged openers ("I was excited to discover," "I came across your posting," "I hope this finds you well").
- The letter must open with something specific about THIS company — a concrete observation about their GTM motion, product positioning, or market move. Not a compliment, not an echo of their mission statement.
- Do not open the letter with "I" as the first word.

FOUR-PARAGRAPH STRUCTURE (no headers, no labels):
1. Opening: one specific observation about this company's GTM situation or challenge (2–3 sentences)
2. Proof: the single most relevant project from Manuel's background, with one concrete detail (3–4 sentences)
3. Contribution: what Manuel would do in the first 30 days, specific to the role and stage (2–3 sentences)
4. Ask: one clear, active sentence requesting next steps — not "I would love to" or "I hope to hear"

OUTPUT: plain prose only, 200–350 words, no markdown formatting of any kind."""


# ---------------------------------------------------------------------------
# Stage 1 prompt: extract JD signals
# ---------------------------------------------------------------------------

def build_stage1_prompt(jd_text: str, question_text: str) -> str:
    return f"""Analyze this job description and extract the following signals as a JSON object.
Return ONLY the JSON object — no explanation, no markdown code fences.

JOB DESCRIPTION:
---
{jd_text}
---

MOTIVATION QUESTION:
---
{question_text}
---

Extract exactly this JSON structure:
{{
  "company_name": "exact company name from the JD",
  "company_slug": "kebab-case slug of company name",
  "stage": "one of: seed | series-a | series-b | series-c | growth | unknown",
  "vertical": "one of: ai | fintech | other",
  "bio_angle": "one of: ai | fintech — choose ai if the company is AI tooling/agents/applied AI; choose fintech if fintech/finance SaaS/payments/banking",
  "headcount_estimate": "number, range, or unknown",
  "key_challenge": "one sentence: the core GTM or commercial challenge this role addresses",
  "role_requirements": ["top 3 requirements from the JD, close paraphrase or verbatim"],
  "most_relevant_proof": "one of: gleef | qbic | artea | oilempire — pick the experience that best maps to the key challenge",
  "relevant_internship_format": "one of: icp-messaging-sprint | channel-experiment-sprint | launch-support-sprint",
  "specific_observation": "one factual sentence about something concrete in their GTM motion — from the job ad language, product description, or implied market positioning. Do not write 'I noticed' or 'I see'. State the observation as a plain fact.",
  "first_30_days_angle": "one sentence: a specific action Manuel could take in the first 30 days that maps directly to the key challenge"
}}

For most_relevant_proof:
- gleef: best for ICP, messaging, tier strategy, B2B SaaS positioning
- qbic: best for market mapping, competitive pattern recognition, screening frameworks
- artea: best for structured analysis, investment memos, hypothesis-driven thinking
- oilempire: best for financial modeling, scenario analysis, quantitative rigor

Return only the JSON. No explanation."""


# ---------------------------------------------------------------------------
# Stage 2 prompt: generate draft
# ---------------------------------------------------------------------------

def build_stage2_prompt(signals: dict, question_text: str) -> str:
    proof_labels = {
        "gleef": "Gleef (ICP, messaging, and channel prioritization project)",
        "qbic": "Qbic (screening 300+ European university spin-offs)",
        "artea": "Artea (investment analysis and memo writing)",
        "oilempire": "OilEmpire (scenario modeling and DCF sensitivity analysis)",
    }
    proof_label = proof_labels.get(signals.get("most_relevant_proof", "gleef"), "Gleef")

    format_labels = {
        "icp-messaging-sprint": "ICP and messaging sprint (6 weeks)",
        "channel-experiment-sprint": "channel experiment sprint (6 weeks)",
        "launch-support-sprint": "launch support sprint (4–8 weeks)",
    }
    format_label = format_labels.get(
        signals.get("relevant_internship_format", "icp-messaging-sprint"),
        "ICP and messaging sprint"
    )

    return f"""Write a cover letter / motivation answer for Manuel Suhrcke for the following application.

EXTRACTED SIGNALS:
- Company: {signals.get('company_name', 'the company')}
- Stage: {signals.get('stage', 'unknown')}
- Vertical: {signals.get('vertical', 'other')}
- Key challenge: {signals.get('key_challenge', '')}
- Role requirements: {', '.join(signals.get('role_requirements', []))}
- Bio angle: {signals.get('bio_angle', 'ai')} (use the {signals.get('bio_angle', 'ai')} bio from your context)
- Most relevant proof: {proof_label}
- Internship format: {format_label}
- Specific observation: {signals.get('specific_observation', '')}
- First 30 days angle: {signals.get('first_30_days_angle', '')}

MOTIVATION QUESTION:
{question_text}

Write exactly four paragraphs with no headers, no labels, no bullet points:

PARAGRAPH 1 (2–3 sentences):
Start with this observation: {signals.get('specific_observation', '')}
Do NOT start the letter with "I". Do NOT open with a compliment or generic praise.
Connect the observation to why this role or challenge matters.

PARAGRAPH 2 (3–4 sentences):
Use ONLY the {proof_label} experience.
Include at least one concrete detail — a number, a named deliverable, or a specific method.
End by connecting the proof to the company's challenge: {signals.get('key_challenge', '')}

PARAGRAPH 3 (2–3 sentences):
State what Manuel would do in the first 30 days. Be action-specific, not aspirational.
Reference the {format_label} format if it fits the role naturally.
Match the company's stage ({signals.get('stage', 'unknown')}) — seed-stage companies need different things than Series B.

PARAGRAPH 4 (1–2 sentences):
One direct, active ask for next steps. Do not write "I would love to" or "I hope to hear from you."
Use active framing: suggest a call, a draft, or a specific next action.

Total length: 200–350 words.
Apply all humanizer rules from your system context.
Output: plain prose only. No markdown. No bold. At most one em dash in the entire letter."""


# ---------------------------------------------------------------------------
# Stage 3 prompt: humanizer audit
# ---------------------------------------------------------------------------

def build_stage3_prompt(draft_text: str) -> str:
    return f"""Audit this cover letter draft against all humanizer rules in your system context.
Return the revised version only. No commentary, no "here is the revised version," no preamble.

Check and fix each of the following:
1. Does the letter open with something specific about the company, or with a generic statement? Fix if generic.
2. Are there any banned words (actually, additionally, testament, landscape, showcasing, actively)? Remove or rewrite.
3. Is there more than one em dash? Convert extras to commas or periods.
4. Is there any bold or italic markdown formatting? Remove all asterisks.
5. Are there "not just X, it's Y" or "not only X but also Y" constructions? Rewrite to direct statements.
6. Does paragraph 2 cite one concrete detail (a number, deliverable, or named method) from the relevant experience? If vague, sharpen it.
7. Does paragraph 3 state a specific action, or an aspiration? If aspirational ("I would aim to," "I hope to contribute"), rewrite to an action ("I would map," "I would run," "I would draft").
8. Does paragraph 4 make an active, direct ask? If it uses "I would love to" or "I hope to hear," rewrite it.
9. Are there filler transition words (Furthermore, Moreover, In addition, Notably, It is worth noting)? Remove them.
10. Does any sentence read like an AI summarizing bullet points rather than a person speaking? Rewrite it.

DRAFT TO AUDIT:
---
{draft_text}
---

Return ONLY the revised cover letter. Plain prose, 200–350 words, no markdown."""


# ---------------------------------------------------------------------------
# Stage 4: programmatic humanizer (regex, no API)
# ---------------------------------------------------------------------------

def programmatic_humanize(text: str) -> tuple[str, list[str]]:
    """
    Apply regex-based humanizer rules. Returns (cleaned_text, [warnings]).
    Warnings are for context-dependent patterns that need a human eye.
    """
    warnings = []

    # Rule 23: "in order to" → "to"
    text = re.sub(r"\bin order to\b", "to", text, flags=re.IGNORECASE)

    # Rule 24: collapse hedging
    text = re.sub(r"\bcould potentially\b", "may", text, flags=re.IGNORECASE)
    text = re.sub(r"\bpotentially could\b", "may", text, flags=re.IGNORECASE)

    # Rule 7: banned filler words
    text = re.sub(r"\bactually,?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\badditionally,?\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bshowcasing\b", "showing", text, flags=re.IGNORECASE)

    # Rule 8: indirect verb replacements
    text = re.sub(r"\bserves as\b", "is", text, flags=re.IGNORECASE)
    text = re.sub(r"\bboasts\b", "has", text, flags=re.IGNORECASE)

    # Rule 27: "At its core"
    text = re.sub(r"\bAt its core[,:]?\s*", "", text, flags=re.IGNORECASE)

    # Rule 28: signposting
    text = re.sub(r"Let's dive in[.,!]?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"Here's what you need to know[.:]?\s*", "", text, flags=re.IGNORECASE)

    # Rule 14: max 1 em dash — replace overflow with comma
    em_positions = [m.start() for m in re.finditer(r"—", text)]
    if len(em_positions) > 1:
        for pos in reversed(em_positions[1:]):
            text = text[:pos] + "," + text[pos + 1 :]

    # Rule 15: strip markdown bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)

    # Rule 9: "not just X, it's Y" → direct
    text = re.sub(
        r"\bnot just ([^,]+),\s*it'?s\s+",
        r"\1 and ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bnot only ([^,]+),?\s*but also\s+",
        r"\1 and ",
        text,
        flags=re.IGNORECASE,
    )

    # Extra filler transitions
    filler = [
        (r"\bFurthermore,?\s+", ""),
        (r"\bMoreover,?\s+", ""),
        (r"\bIn addition,?\s+", ""),
        (r"\bNotably,?\s+", ""),
        (r"\bIt is worth noting that\s+", ""),
        (r"\bIt should be noted that\s+", ""),
        (r"\bIt is important to note that\s+", ""),
        (r"\bNeedless to say,?\s+", ""),
        (r"\bOf course,?\s+", ""),
        (r"\bCertainly,?\s+", ""),
    ]
    for pattern, replacement in filler:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean up spacing from removals
    text = re.sub(r"  +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Re-capitalize sentence starts after cleanup
    def cap_sentence(match):
        return match.group(0)[0] + match.group(1).upper() + match.group(2)

    text = re.sub(r"([.!?]\s+)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)

    # Capitalize first character of the whole text
    if text:
        text = text[0].upper() + text[1:]

    text = text.strip()

    # Context-dependent warnings (flag for manual review)
    warn_patterns = [
        (r"\btestament\b", "Rule 7: 'testament' found — rewrite manually"),
        (r"\blandscape\b", "Rule 7: 'landscape' (metaphor) found — rewrite manually"),
        (r"\bI am passionate\b", "Generic enthusiasm: 'I am passionate' — rewrite"),
        (r"\bI love\b", "Generic enthusiasm: 'I love' — rewrite"),
        (r"\bexcited to\b", "Hedged opener: 'excited to' — rewrite"),
        (r"\bI hope\b", "Passive ask: 'I hope' — rewrite to active ask"),
        (r"\bI would love to\b", "Passive ask: 'I would love to' — rewrite to active ask"),
        (r"\bfeatures\b", "Rule 8: 'features' (as verb) may need replacing with 'has' or 'includes'"),
    ]
    for pattern, msg in warn_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            warnings.append(msg)

    return text, warnings


# ---------------------------------------------------------------------------
# Claude API call (shared across all stages)
# ---------------------------------------------------------------------------

def call_claude(
    client: anthropic.Anthropic,
    system_blocks: list,
    user_message: str,
    max_tokens: int = 1024,
) -> tuple[str, dict]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system_blocks,
        messages=[{"role": "user", "content": user_message}],
    )

    text = next((b.text for b in response.content if b.type == "text"), "")
    usage = {
        "input": response.usage.input_tokens,
        "cached": getattr(response.usage, "cache_read_input_tokens", 0),
        "cache_created": getattr(response.usage, "cache_creation_input_tokens", 0),
        "output": response.usage.output_tokens,
    }
    return text, usage


def accumulate_usage(total: dict, usage: dict) -> None:
    for key in total:
        total[key] = total.get(key, 0) + usage.get(key, 0)


# ---------------------------------------------------------------------------
# Output formatter
# ---------------------------------------------------------------------------

def format_output(signals: dict, question: str, letter: str, usage: dict) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    company = signals.get("company_name", "Unknown")

    meta_lines = [
        "---",
        f"company: {company}",
        f"stage: {signals.get('stage', 'unknown')}",
        f"vertical: {signals.get('vertical', 'other')}",
        f"bio_angle: {signals.get('bio_angle', 'ai')}",
        f"most_relevant_proof: {signals.get('most_relevant_proof', '')}",
        f"internship_format: {signals.get('relevant_internship_format', '')}",
        f"generated: {generated_at}",
        f"model: {MODEL}",
        f"tokens_input: {usage.get('input', 0)}",
        f"tokens_cached: {usage.get('cached', 0)}",
        f"tokens_output: {usage.get('output', 0)}",
        "---",
        "",
        f"# Cover letter / motivation answer — {company}",
        "",
        f"**Question:** {question}",
        "",
        "---",
        "",
        letter,
    ]
    return "\n".join(meta_lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    load_env_file(ENV_FILE)

    parser = argparse.ArgumentParser(
        description="Generate a humanized cover letter for a startup job application.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/generate_cover_letter.py \\
    --jd path/to/jd.txt \\
    --question "What motivates you to join Basis Theory?"

  python scripts/generate_cover_letter.py \\
    --jd path/to/jd.txt \\
    --question-file path/to/q.txt \\
    --dry-run --verbose

  python scripts/generate_cover_letter.py \\
    --jd path/to/jd.txt \\
    --question "Why us?" \\
    --company "Adaptive ML"
        """,
    )
    parser.add_argument("--jd", required=True, help="Path to .txt file with the raw job description")
    parser.add_argument("--question", default=None, help="Motivation question as a quoted string")
    parser.add_argument("--question-file", dest="question_file", default=None, help="Path to .txt file with the motivation question")
    parser.add_argument("--dry-run", action="store_true", help="Print output without writing to disk")
    parser.add_argument("--verbose", action="store_true", help="Print intermediate stage outputs")
    parser.add_argument("--company", default=None, help="Override company name for the output slug")

    args = parser.parse_args()

    # Validate input files
    jd_path = Path(args.jd)
    if not jd_path.is_file():
        sys.exit(f"JD file not found: {jd_path}")

    if args.question and args.question_file:
        sys.exit("Provide --question OR --question-file, not both.")
    if not args.question and not args.question_file:
        sys.exit("Provide either --question or --question-file.")

    jd_text = jd_path.read_text(encoding="utf-8").strip()

    if args.question:
        question_text = args.question.strip()
    else:
        q_path = Path(args.question_file)
        if not q_path.is_file():
            sys.exit(f"Question file not found: {q_path}")
        question_text = q_path.read_text(encoding="utf-8").strip()

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set. Add it to .env or your environment.")

    # Load positioning and build the cached system block
    positioning = load_positioning()
    client = anthropic.Anthropic(api_key=api_key)

    system_blocks = [
        {
            "type": "text",
            "text": build_system_prompt(positioning),
            "cache_control": {"type": "ephemeral"},
        }
    ]

    total_usage: dict = {"input": 0, "cached": 0, "cache_created": 0, "output": 0}

    # ------------------------------------------------------------------
    # Stage 1: extract JD signals
    # ------------------------------------------------------------------
    print("Stage 1: Extracting JD signals...")
    signals_text, usage1 = call_claude(
        client,
        system_blocks,
        build_stage1_prompt(jd_text, question_text),
        max_tokens=512,
    )
    accumulate_usage(total_usage, usage1)

    # Strip possible markdown code fences from the response
    signals_text_clean = re.sub(r"^```(?:json)?\s*", "", signals_text.strip(), flags=re.IGNORECASE)
    signals_text_clean = re.sub(r"\s*```$", "", signals_text_clean.strip())

    try:
        signals = json.loads(signals_text_clean)
    except json.JSONDecodeError:
        print("  [retry] JSON parse failed, retrying...", file=sys.stderr)
        signals_text2, usage1b = call_claude(
            client,
            system_blocks,
            build_stage1_prompt(jd_text, question_text) + "\n\nIMPORTANT: Return raw JSON only, no markdown fences.",
            max_tokens=512,
        )
        accumulate_usage(total_usage, usage1b)
        signals_text2_clean = re.sub(r"^```(?:json)?\s*", "", signals_text2.strip(), flags=re.IGNORECASE)
        signals_text2_clean = re.sub(r"\s*```$", "", signals_text2_clean.strip())
        try:
            signals = json.loads(signals_text2_clean)
        except json.JSONDecodeError as e:
            sys.exit(f"Stage 1 failed to return valid JSON after retry: {e}\nResponse was:\n{signals_text2}")

    if args.company:
        signals["company_name"] = args.company
        signals["company_slug"] = slugify(args.company)

    if args.verbose:
        print(f"  Signals:\n{json.dumps(signals, indent=2)}")

    # ------------------------------------------------------------------
    # Stage 2: generate draft
    # ------------------------------------------------------------------
    print("Stage 2: Generating draft...")
    draft_text, usage2 = call_claude(
        client,
        system_blocks,
        build_stage2_prompt(signals, question_text),
        max_tokens=1024,
    )
    accumulate_usage(total_usage, usage2)

    if args.verbose:
        print(f"\n--- DRAFT ---\n{draft_text}\n")

    # ------------------------------------------------------------------
    # Stage 3: humanizer audit (LLM pass)
    # ------------------------------------------------------------------
    print("Stage 3: Humanizer audit pass...")
    audited_text, usage3 = call_claude(
        client,
        system_blocks,
        build_stage3_prompt(draft_text),
        max_tokens=1024,
    )
    accumulate_usage(total_usage, usage3)

    if args.verbose:
        print(f"\n--- POST-AUDIT ---\n{audited_text}\n")

    # ------------------------------------------------------------------
    # Stage 4: programmatic regex pass
    # ------------------------------------------------------------------
    print("Stage 4: Applying programmatic humanizer rules...")
    final_text, warnings = programmatic_humanize(audited_text)

    for w in warnings:
        print(f"  [WARN] {w}", file=sys.stderr)

    word_count = len(final_text.split())
    if word_count < MIN_WORDS or word_count > MAX_WORDS:
        print(
            f"  [WARN] Word count is {word_count} (target: {MIN_WORDS}–{MAX_WORDS})",
            file=sys.stderr,
        )

    # ------------------------------------------------------------------
    # Assemble and save/print output
    # ------------------------------------------------------------------
    output_content = format_output(signals, question_text, final_text, total_usage)

    slug = signals.get("company_slug") or slugify(signals.get("company_name", "unknown"))
    output_path = OUTPUT_DIR / f"{slug}.md"

    token_summary = (
        f"Tokens — input: {total_usage['input']} | "
        f"cached: {total_usage['cached']} | "
        f"cache_created: {total_usage['cache_created']} | "
        f"output: {total_usage['output']}"
    )

    if args.dry_run:
        # Encode to ASCII for safe Windows console printing
        safe_output = output_content.encode("ascii", "replace").decode("ascii")
        print(f"\n{'=' * 60}")
        print(f"[dry-run] Would write to: {output_path}")
        print(f"Words: {word_count}")
        print()
        print(safe_output)
        print(f"\n{token_summary}")
    else:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content, encoding="utf-8")
        print(f"\nWrote: {output_path}")
        print(f"Words: {word_count}")
        print(token_summary)
        if warnings:
            print(f"\n{len(warnings)} manual review warning(s) printed above.")
        print("\nNext step: run /humanize on the output for a final manual check before submitting.")


if __name__ == "__main__":
    main()
