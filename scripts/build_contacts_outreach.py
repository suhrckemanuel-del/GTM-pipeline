"""Generate contacts.csv and outreach.csv for batch-01 + batch-02 targets.

Preserves work_email, email_status, and email_source when regenerating rows
that match the same (company_id, role) as the existing contacts.csv.

Split test groups (by headcount midpoint):
  group_a — small teams (≤60 midpoint) → CEO/Founder approach
  group_b — large teams (>60 midpoint) → GTM Lead approach
"""
from __future__ import annotations

import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Batch-01 targets  (send 2026-04-11, FU 2026-04-15, FU2 2026-04-20)
# ---------------------------------------------------------------------------
BATCH01 = {
    "touch1": "2026-04-11",
    "fu1":    "2026-04-15",
    "fu2":    "2026-04-20",
    "version": "v1-batch-01",
}

# ---------------------------------------------------------------------------
# Batch-02 targets  (send 2026-04-18, FU 2026-04-22, FU2 2026-04-27)
# ---------------------------------------------------------------------------
BATCH02 = {
    "touch1": "2026-04-18",
    "fu1":    "2026-04-22",
    "fu2":    "2026-04-27",
    "version": "v1-batch-02",
}

# ---------------------------------------------------------------------------
# (company_id, roles, batch_meta, split_test_group)
# group_a = small teams (≤60 headcount midpoint) → CEO-direct approach
# group_b = large teams (>60 headcount midpoint) → GTM-lead approach
# ---------------------------------------------------------------------------
ALL_COMPANIES: list[tuple[int, list[str], dict, str]] = [
    # --- Batch 01 ---
    (1,  ["Founder/CEO", "Commercial lead (GTM)", "People/Talent lead"], BATCH01, "group_a"),   # Gleef      midpoint ~27
    (2,  ["CEO/Co-founder", "Head of Growth or GTM", "People partner"],  BATCH01, "group_a"),   # Nexus      midpoint ~25
    (3,  ["CEO/Co-founder", "Head of Sales or GTM", "Talent lead"],      BATCH01, "group_a"),   # Enginy     midpoint ~30
    (7,  ["CEO/Co-founder", "GTM/Revenue lead", "People"],               BATCH01, "group_a"),   # Paid.ai    midpoint ~50
    (21, ["CEO/Co-founder", "VP Sales or GTM", "People"],                BATCH01, "group_b"),   # Clerq      midpoint ~65
    (23, ["CEO/Co-founder", "GTM lead", "People"],                       BATCH01, "group_b"),   # Payabli    midpoint ~115
    (24, ["CEO/Co-founder", "GTM lead", "People"],                       BATCH01, "group_a"),   # Basis Th.  midpoint ~45
    (25, ["CEO/Co-founder", "Commercial lead", "People"],                BATCH01, "group_a"),   # OneNext    midpoint ~40
    (4,  ["CEO/Co-founder", "VP Marketing or GTM", "People"],            BATCH01, "group_b"),   # Kestra     midpoint ~115
    (26, ["CEO/Co-founder", "GTM lead", "People"],                       BATCH01, "group_a"),   # autone     midpoint ~60
    # --- Batch 02 ---
    (5,  ["CEO/Co-founder", "VP Product or GTM", "People"],              BATCH02, "group_b"),   # FlexAI     midpoint ~60 (border → group_b)
    (6,  ["CEO/Co-founder", "GTM lead", "People"],                       BATCH02, "group_b"),   # Maisa AI   midpoint ~70
    (8,  ["CEO/Co-founder", "GTM lead", "People"],                       BATCH02, "group_a"),   # Octonomy   midpoint ~45
    (9,  ["CEO/Co-founder", "GTM lead", "People"],                       BATCH02, "group_a"),   # Cognee     midpoint ~37
    (10, ["CEO/Co-founder", "VP Marketing or GTM", "People"],            BATCH02, "group_b"),   # Lovable    midpoint ~85
    (11, ["CEO/Co-founder", "GTM lead", "People"],                       BATCH02, "group_b"),   # BFL        midpoint ~70
    (13, ["CEO/Co-founder", "VP Marketing or GTM", "People"],            BATCH02, "group_b"),   # Lakera AI  midpoint ~60 (border → group_b)
    (14, ["CEO/Co-founder", "VP Marketing or GTM", "People"],            BATCH02, "group_b"),   # n8n        midpoint ~150
    (15, ["CEO/Co-founder", "GTM lead", "People"],                       BATCH02, "group_a"),   # Adaptive   midpoint ~32
    (22, ["CEO/Co-founder", "VP Sales or GTM", "People"],                BATCH02, "group_b"),   # OpenFX     midpoint ~85
]

CONTACT_HEADER = [
    "contact_id",
    "company_id",
    "name",
    "role",
    "channel",
    "profile_url",
    "warmness_cold_warm",
    "notes",
    "work_email",
    "email_status",
    "email_source",
    "split_test_group",
]

OUTREACH_HEADER = [
    "outreach_id",
    "company_id",
    "contact_id",
    "touch_number",
    "message_version",
    "channel",
    "sent_date",
    "follow_up_1_date",
    "follow_up_2_date",
    "response_status",
    "next_action",
]


def _load_contact_merge(contacts_path: Path) -> dict[tuple[int, str], dict[str, str]]:
    """Load prior row data keyed by (company_id, role) for non-destructive regen."""
    if not contacts_path.is_file():
        return {}
    merge: dict[tuple[int, str], dict[str, str]] = {}
    with contacts_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                cid = int(row.get("company_id", "").strip())
            except ValueError:
                continue
            role = (row.get("role") or "").strip()
            key = (cid, role)
            merge[key] = {
                "name": (row.get("name") or "").strip(),
                "profile_url": (row.get("profile_url") or "").strip(),
                "work_email": (row.get("work_email") or "").strip(),
                "email_status": (row.get("email_status") or "").strip(),
                "email_source": (row.get("email_source") or "").strip(),
            }
    return merge


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    contacts_path = root / "pipeline" / "contacts.csv"
    outreach_path = root / "pipeline" / "outreach.csv"

    prior = _load_contact_merge(contacts_path)

    contact_rows: list[list[object]] = []
    outreach_rows: list[list[object]] = []
    contact_id = 1
    outreach_id = 1

    for company_id, roles, batch, group in ALL_COMPANIES:
        for role in roles:
            extras = prior.get(
                (company_id, role),
                {
                    "name": "",
                    "profile_url": "",
                    "work_email": "",
                    "email_status": "",
                    "email_source": "",
                },
            )
            name = extras["name"] or "TO_RESEARCH"
            if name.upper() == "TO_RESEARCH":
                name = "TO_RESEARCH"

            contact_rows.append([
                contact_id,
                company_id,
                name,
                role,
                "LinkedIn",
                extras["profile_url"],
                "cold",
                "Find on LinkedIn; personalize first line",
                extras["work_email"],
                extras["email_status"],
                extras["email_source"],
                group,
            ])
            outreach_rows.append([
                outreach_id,
                company_id,
                contact_id,
                1,
                batch["version"],
                "LinkedIn",
                batch["touch1"],
                batch["fu1"],
                batch["fu2"],
                "planned",
                "Send touch 1; log reply; schedule touch 2-3",
            ])
            contact_id += 1
            outreach_id += 1

    with contacts_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(CONTACT_HEADER)
        w.writerows(contact_rows)

    with outreach_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(OUTREACH_HEADER)
        w.writerows(outreach_rows)

    print(f"Wrote {len(contact_rows)} contacts ({sum(1 for r in contact_rows if r[11]=='group_a')} group_a, "
          f"{sum(1 for r in contact_rows if r[11]=='group_b')} group_b), "
          f"{len(outreach_rows)} outreach rows")


if __name__ == "__main__":
    main()
