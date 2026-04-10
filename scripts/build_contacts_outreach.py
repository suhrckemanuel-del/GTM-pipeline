"""Generate contacts.csv, insights.csv rows, and outreach.csv for top 10 targets."""
import csv
from pathlib import Path

# company_id, roles to try (2-3 each)
TOP10 = [
    (1, ["Founder/CEO", "Commercial lead (GTM)", "People/Talent lead"]),
    (2, ["CEO/Co-founder", "Head of Growth or GTM", "People partner"]),
    (3, ["CEO/Co-founder", "Head of Sales or GTM", "Talent lead"]),
    (7, ["CEO/Co-founder", "GTM/Revenue lead", "People"]),
    (21, ["CEO/Co-founder", "VP Sales or GTM", "People"]),
    (23, ["CEO/Co-founder", "GTM lead", "People"]),
    (24, ["CEO/Co-founder", "GTM lead", "People"]),
    (25, ["CEO/Co-founder", "Commercial lead", "People"]),
    (4, ["CEO/Co-founder", "VP Marketing or GTM", "People"]),
    (26, ["CEO/Co-founder", "GTM lead", "People"]),
]

TOUCH1 = "2026-04-11"
FU1 = "2026-04-15"
FU2 = "2026-04-20"


def main():
    root = Path(__file__).resolve().parents[1]
    contacts_path = root / "pipeline" / "contacts.csv"
    outreach_path = root / "pipeline" / "outreach.csv"

    contact_rows = []
    outreach_rows = []
    cid = 1
    oid = 1
    for company_id, roles in TOP10:
        for role in roles:
            contact_rows.append(
                [
                    cid,
                    company_id,
                    "TO_RESEARCH",
                    role,
                    "LinkedIn",
                    "",
                    "cold",
                    "Find on LinkedIn; personalize first line",
                ]
            )
            outreach_rows.append(
                [
                    oid,
                    company_id,
                    cid,
                    1,
                    "v1-batch-01",
                    "LinkedIn",
                    TOUCH1,
                    FU1,
                    FU2,
                    "planned",
                    "Send touch 1; log reply; schedule touch 2-3",
                ]
            )
            cid += 1
            oid += 1

    with contacts_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "contact_id",
                "company_id",
                "name",
                "role",
                "channel",
                "profile_url",
                "warmness_cold_warm",
                "notes",
            ]
        )
        w.writerows(contact_rows)

    with outreach_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
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
        )
        w.writerows(outreach_rows)

    print(f"Wrote {len(contact_rows)} contacts, {len(outreach_rows)} outreach rows")


if __name__ == "__main__":
    main()
