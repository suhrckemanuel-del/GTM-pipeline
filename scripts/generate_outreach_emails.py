"""
Generate send-ready email CSVs and LinkedIn message file from existing draft .md files.

Split test:
  group_a (small teams, ≤60 headcount midpoint) -> CEO/Founder Touch 1
  group_b (large teams, >60 headcount midpoint) -> GTM Lead Touch 1

Outputs:
  outreach/ready-to-send/group-a-small-ceo.csv
  outreach/ready-to-send/group-b-large-gtm.csv
  outreach/ready-to-send/linkedin-messages.md

Usage:
  python scripts/generate_outreach_emails.py [--dry-run]
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# company_id -> (batch_folder, draft_filename, company_display_name)
# ---------------------------------------------------------------------------
COMPANY_DRAFT_MAP: dict[int, tuple[str, str, str]] = {
    1:  ("batch-01", "gleef.md",            "Gleef"),
    2:  ("batch-01", "nexus.md",             "Nexus"),
    3:  ("batch-01", "enginy.md",            "Enginy"),
    4:  ("batch-01", "kestra.md",            "Kestra"),
    5:  ("batch-02", "flexai.md",            "FlexAI"),
    6:  ("batch-02", "maisa-ai.md",          "Maisa AI"),
    7:  ("batch-01", "paid-ai.md",           "Paid.ai"),
    8:  ("batch-02", "octonomy.md",          "Octonomy"),
    9:  ("batch-02", "cognee.md",            "Cognee"),
    10: ("batch-02", "lovable.md",           "Lovable"),
    11: ("batch-02", "black-forest-labs.md", "Black Forest Labs"),
    13: ("batch-02", "lakera-ai.md",         "Lakera AI"),
    14: ("batch-02", "n8n.md",               "n8n"),
    15: ("batch-02", "adaptive-ml.md",       "Adaptive ML"),
    21: ("batch-01", "clerq.md",             "Clerq"),
    22: ("batch-02", "openfx.md",            "OpenFX"),
    23: ("batch-01", "payabli.md",           "Payabli"),
    24: ("batch-01", "basis-theory.md",      "Basis Theory"),
    25: ("batch-01", "onenext.md",           "OneNext"),
    26: ("batch-01", "autone.md",            "autone"),
}

# Personalized subject lines per company (group_a = CEO approach, group_b = GTM approach)
SUBJECTS: dict[int, str] = {
    # group_a — CEO-direct
    1:  "one thought on Gleef's tier messaging",
    2:  "one thought on Nexus's vertical story",
    3:  "one thought on Enginy's ICP narrative",
    7:  "one thought on Paid.ai's buyer story",
    8:  "one thought on Octonomy's positioning",
    9:  "one thought on Cognee's knowledge graph story",
    15: "one thought on Adaptive ML's buyer narrative",
    24: "one thought on Basis Theory's developer messaging",
    25: "one thought on OneNext's go-to-market angle",
    26: "one thought on autone's retail positioning",
    # group_b — GTM-lead
    4:  "Kestra workflow messaging — quick test idea",
    5:  "FlexAI workload story — split-funnel idea",
    6:  "Maisa AI positioning — one experiment",
    10: "Lovable messaging clarity — quick thought",
    11: "Black Forest Labs GTM — one experiment",
    13: "Lakera AI positioning — quick idea",
    14: "n8n OSS-to-commercial boundary — test idea",
    21: "Clerq vertical proof — quick messaging test",
    22: "OpenFX GTM story — one experiment",
    23: "Payabli embedded finance messaging — quick idea",
}

# Keywords used to identify each persona section in the .md files
CEO_KEYWORDS    = ["founder", "ceo", "co-founder", "commercial lead"]
GTM_KEYWORDS    = ["gtm", "sales", "growth", "marketing", "vp product", "vp marketing",
                   "technical gtm", "mid-market", "commercial", "revenue", "partnerships", "enterprise"]
PEOPLE_KEYWORDS = ["people", "talent"]


def parse_draft(md_path: Path) -> dict[str, str]:
    """
    Parse a company draft .md file.
    Returns dict with keys 'ceo', 'gtm', 'people' mapped to their Touch 1 body text.
    """
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    sections: dict[str, str] = {}
    current_section: str | None = None
    in_touch1 = False
    touch1_lines: list[str] = []

    def flush():
        nonlocal touch1_lines, current_section
        if current_section and touch1_lines:
            body = "\n".join(touch1_lines).strip()
            if body:
                sections[current_section] = body
        touch1_lines = []

    for i, line in enumerate(lines):
        # Detect H2 section (##) — new persona
        if line.startswith("## "):
            flush()
            in_touch1 = False
            heading = line[3:].lower().strip()
            if any(k in heading for k in CEO_KEYWORDS):
                current_section = "ceo"
            elif any(k in heading for k in PEOPLE_KEYWORDS):
                current_section = "people"
            elif any(k in heading for k in GTM_KEYWORDS):
                current_section = "gtm"
            else:
                current_section = None
            continue

        # Detect Touch markers (###)
        if line.startswith("### "):
            touch_name = line[4:].lower().strip()
            if touch_name == "touch 1":
                in_touch1 = True
                touch1_lines = []
            elif in_touch1:
                # Entering Touch 2 or 3 — stop collecting
                flush()
                in_touch1 = False
            continue

        if in_touch1 and current_section:
            touch1_lines.append(line)

    flush()
    return sections


def first_name(full: str) -> str:
    """Return first word of a name, or empty string if TO_RESEARCH."""
    if not full or full.strip().upper() == "TO_RESEARCH":
        return ""
    return full.strip().split()[0]


def role_to_bucket(role: str) -> str:
    r = role.lower()
    if any(k in r for k in ["founder", "ceo", "co-founder"]):
        return "ceo"
    if any(k in r for k in ["people", "talent", "hr"]):
        return "people"
    return "gtm"


def main() -> None:
    root = Path(__file__).resolve().parents[1]

    p = argparse.ArgumentParser(description="Generate send-ready email CSVs from outreach drafts")
    p.add_argument("--dry-run", action="store_true", help="Print previews, don't write files")
    args = p.parse_args()

    contacts_path = root / "pipeline" / "contacts.csv"
    if not contacts_path.is_file():
        print("Run build_contacts_outreach.py first.", file=sys.stderr)
        sys.exit(1)

    with contacts_path.open(newline="", encoding="utf-8-sig") as f:
        contacts = list(csv.DictReader(f))

    out_dir = root / "outreach" / "ready-to-send"
    if not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    # Only target the 1 contact per company that matches the split-test approach
    # group_a -> CEO bucket, group_b -> GTM bucket
    target_bucket = {"group_a": "ceo", "group_b": "gtm"}

    email_rows_a: list[dict] = []
    email_rows_b: list[dict] = []
    linkedin_blocks: list[str] = []
    warnings: list[str] = []

    # Track which companies we've already output (one contact per company for the test)
    seen: set[int] = set()

    for row in contacts:
        cid_str = (row.get("company_id") or "").strip()
        if not cid_str:
            continue
        cid = int(cid_str)

        group = (row.get("split_test_group") or "").strip()
        if group not in target_bucket:
            continue

        bucket = role_to_bucket(row.get("role", ""))
        if bucket != target_bucket[group]:
            continue  # skip non-target personas for this split

        if cid in seen:
            continue
        seen.add(cid)

        draft_info = COMPANY_DRAFT_MAP.get(cid)
        if not draft_info:
            warnings.append(f"No draft mapping for company_id={cid}")
            continue

        batch_folder, filename, company_name = draft_info
        md_path = root / "outreach" / "drafts" / batch_folder / filename
        if not md_path.exists():
            warnings.append(f"Draft not found: {md_path}")
            continue

        sections = parse_draft(md_path)
        body_raw = sections.get(bucket)
        if not body_raw:
            warnings.append(f"No {bucket} Touch 1 found in {md_path.name}")
            continue

        name = (row.get("name") or "").strip()
        fn = first_name(name)
        email = (row.get("work_email") or "").strip()
        profile_url = (row.get("profile_url") or "").strip()
        send_date = ""

        # Substitute {{FirstName}} — if unknown, leave placeholder
        body = body_raw.replace("{{FirstName}}", fn if fn else "{{FirstName}}")

        # Remove markdown bold markers for plain-text email
        body_plain = re.sub(r"\*\*(.+?)\*\*", r"\1", body)
        body_plain = re.sub(r"\*(.+?)\*", r"\1", body_plain)

        subject = SUBJECTS.get(cid, f"GTM thought — {company_name}")

        record = {
            "company_id":       cid,
            "company":          company_name,
            "split_test_group": group,
            "to_name":          name if name and name.upper() != "TO_RESEARCH" else "",
            "to_email":         email,
            "subject":          subject,
            "body":             body_plain,
            "send_date":        send_date,
            "sent":             "no",
        }

        if group == "group_a":
            email_rows_a.append(record)
        else:
            email_rows_b.append(record)

        # LinkedIn block (use markdown body for richness)
        li_block = (
            f"### {company_name} — {name} ({row.get('role', '')})\n"
            f"{'LinkedIn: ' + profile_url if profile_url else 'LinkedIn: [TO_FIND]'}\n\n"
            f"{body}\n"
        )
        linkedin_blocks.append(li_block)

        if args.dry_run:
            def _safe(s: str) -> str:
                return s.encode("ascii", "replace").decode("ascii")
            print(f"\n{'='*60}")
            print(f"[{group.upper()}] {company_name}  ({bucket.upper()} bucket)")
            print(f"To:      {name} <{email or 'NO_EMAIL'}>")
            print(f"Subject: {subject}")
            print(f"Body:\n{_safe(body_plain)}")

    if warnings:
        print("\nWarnings:", file=sys.stderr)
        for w in warnings:
            print(f"  {w}", file=sys.stderr)

    if args.dry_run:
        print(f"\n--- Summary ---")
        print(f"group_a emails: {len(email_rows_a)}")
        print(f"group_b emails: {len(email_rows_b)}")
        print(f"LinkedIn blocks: {len(linkedin_blocks)}")
        print("--dry-run: no files written.")
        return

    csv_fields = ["company_id", "company", "split_test_group", "to_name", "to_email",
                  "subject", "body", "send_date", "sent"]

    path_a = out_dir / "group-a-small-ceo.csv"
    with path_a.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(email_rows_a)
    print(f"Wrote {len(email_rows_a)} rows -> {path_a}")

    path_b = out_dir / "group-b-large-gtm.csv"
    with path_b.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(email_rows_b)
    print(f"Wrote {len(email_rows_b)} rows -> {path_b}")

    li_path = out_dir / "linkedin-messages.md"
    li_content = "# LinkedIn Touch 1 Messages\n\nSend manually from linkedin.com/in/manuel-suhrcke-80b9a9285\n\n---\n\n"
    li_content += "\n---\n\n".join(linkedin_blocks)
    li_path.write_text(li_content, encoding="utf-8")
    print(f"Wrote {len(linkedin_blocks)} LinkedIn blocks -> {li_path}")


if __name__ == "__main__":
    main()
