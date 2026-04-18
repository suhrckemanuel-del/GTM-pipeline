"""
Rewrite all 18 LinkedIn DMs in pipeline/akirolabs/insights.csv.
Two-pass humanization: eliminate AI-pattern violations, tighten to <=60 words.
Sign-off standardized to "— Manuel" throughout.
"""

import csv

CSV_PATH = r"C:\Users\User\Desktop\GTM-internship-outreach\pipeline\akirolabs\insights.csv"

NEW_DMS = {
    "1": (
        "Hi — Continental's procurement team is refreshing category strategies across 50+ countries "
        "while the spend mix shifts from legacy auto parts to software-defined vehicle tech. That cycle "
        "typically runs 4–6 weeks per category. Bertelsmann used Akirolabs across 7 divisions to cut it "
        "by up to 90%. Happy to show how it maps to Continental's setup — 15 minutes. — Manuel"
    ),
    "2": (
        "Hi — aligning category strategies across legacy ZF divisions and the WABCO integration while "
        "the supply base shifts toward electrification puts serious pressure on any manual refresh cycle. "
        "Bertelsmann used Akirolabs across 7 divisions to cut that cycle by up to 90%. If a 15-minute "
        "walkthrough would be useful, I'm glad to set one up. — Manuel"
    ),
    "3": (
        "Hi — Schaeffler's automotive and industrial divisions run separate category strategies across "
        "70+ plants, with diverging market dynamics in each. Bertelsmann used Akirolabs across 7 divisions "
        "to cut that refresh cycle by up to 90%. If a short walkthrough would be useful, I can send over "
        "the details. — Manuel"
    ),
    "4": (
        "Hi — refreshing energy or logistics category strategies across 150+ MAHLE sites while supply "
        "markets shift toward e-mobility is a cycle that outpaces static slide decks. Bertelsmann used "
        "Akirolabs across 7 divisions to cut it by up to 90%. If 15 minutes to walk through how it maps "
        "to MAHLE's footprint would be useful, I'm available. — Manuel"
    ),
    "5": (
        "Hi — feedstock and energy prices at Evonik can move 15–20% in a quarter. A 6-week strategy "
        "refresh cycle turns that into a standing gap. Bertelsmann used Akirolabs across 7 divisions to "
        "cut that cycle by up to 90%. If a short demo for your most volatile categories would be useful, "
        "I can arrange it. — Manuel"
    ),
    "6": (
        "Hi — re-baselining category strategies across every remaining Lanxess business unit after the "
        "engineering plastics sale means restarting from scratch across 30+ countries of indirect spend, "
        "under cost pressure. Bertelsmann used Akirolabs across 7 divisions to cut that cycle by up to "
        "90%. If a 20-minute walkthrough would be useful, I can schedule one. — Manuel"
    ),
    "7": (
        "Hi — refreshing category strategies across dozens of indirect spend areas in parallel, while "
        "running a cost transformation with banking compliance layers on top, means the backlog grows "
        "faster than the team can clear it. Bertelsmann used Akirolabs across 7 divisions to cut that "
        "cycle by up to 90%. I can walk through the case in 15 minutes if useful. — Manuel"
    ),
    "8": (
        "Hi — aligning category strategies for IT services spend across Union Investment, R+V, TeamBank, "
        "and other DZ Bank group entities involves reconciling siloed spend data, divergent market views, "
        "and BaFin compliance requirements. Bertelsmann used Akirolabs across 7 divisions to cut that "
        "cycle by up to 90%. A short demo could show how the same approach applies here. — Manuel"
    ),
    "9": (
        "Hi — Fresenius runs category strategy refreshes across Kabi, Helios, Vamed, and Medical Care, "
        "each with separate supplier databases and clinical requirements. Cross-segment volume leverage "
        "rarely surfaces in that structure. Bertelsmann used Akirolabs across 7 divisions to cut that "
        "cycle by up to 90%. If a quick walkthrough would be useful, I can send the details. — Manuel"
    ),
    "10": (
        "Hi — integrating acquired entities at Sartorius means reconciling fragmented ERPs, divergent "
        "supplier bases, and misaligned category strategies simultaneously. That coordination overhead "
        "compounds as the company scales. Bertelsmann used Akirolabs across 7 divisions to cut strategy "
        "refresh time by up to 90%. If a 15-minute walkthrough of how it applies to Sartorius would be "
        "useful, I'm available. — Manuel"
    ),
    "11": (
        "Hi — EnBW's capex timeline for grid modernization and renewables means category strategies for "
        "HVDC components, transformers, and construction services need to stay current as copper prices "
        "and supplier capacity shift. Bertelsmann used Akirolabs across 7 divisions to cut strategy "
        "refresh time by up to 90%. A 15-minute look at how it applies to EnBW's category taxonomy "
        "would be straightforward to arrange. — Manuel"
    ),
    "12": (
        "Hi — Verbund's renewable expansion puts pressure on category strategies for turbine MRO and "
        "construction services across Central Europe, where supplier markets are moving fast. Bertelsmann "
        "used Akirolabs across 7 divisions to cut strategy refresh time by up to 90%. If a 15-minute "
        "walkthrough of how it applies to Verbund's setup would be useful, I can arrange it. — Manuel"
    ),
    "13": (
        "Hi — ING Germany's IT services spend spans cloud infrastructure, cybersecurity vendors, and "
        "software licensing across a digital-first model. Vendor markets in each of those sub-categories "
        "shift faster than a 5-week manual strategy cycle can track. Bertelsmann used Akirolabs across "
        "7 divisions to cut that cycle by up to 90%. I can walk through how it applies in 15 minutes. — Manuel"
    ),
    "14": (
        "Hi — OMV is rebuilding category strategies across dozens of spend areas simultaneously while "
        "pivoting from oil and gas to sustainable fuels and chemicals. That re-baselining at spreadsheet "
        "speed creates gaps in sourcing decisions. Bertelsmann used Akirolabs across 7 divisions to cut "
        "that cycle by up to 90%. I can show a short demo tailored to OMV's transformation. — Manuel"
    ),
    "15": (
        "Hi — post-simplification, Clariant is rebuilding category strategies for energy, logistics, and "
        "MRO while managing feedstock and energy price swings that can move cost by tens of millions per "
        "quarter. A 6-week manual cycle leaves those strategies perpetually behind the market. Bertelsmann "
        "used Akirolabs across 7 divisions to cut that cycle by up to 90%. I can walk through how in "
        "15 minutes. — Manuel"
    ),
    "16": (
        "Hi — Knorr-Bremse's Rail Systems and Commercial Vehicle Systems divisions share overlapping "
        "supplier markets but maintain separate category strategies. Each refresh cycle duplicates effort "
        "without surfacing cross-divisional leverage. Bertelsmann used Akirolabs across 7 divisions to "
        "cut that cycle by up to 90%. If a 15-minute walkthrough of how it applies to Knorr-Bremse would "
        "be useful, I can set one up. — Manuel"
    ),
    "17": (
        "Hi — Wacker's energy procurement strategy covers fixed, spot, and PPA positions across "
        "Burghausen, Nünchritz, and Charleston. When European energy prices move mid-quarter, a 4-week "
        "refresh cycle means sourcing decisions lag the market. Bertelsmann used Akirolabs across 7 "
        "divisions to cut that cycle by up to 90%. A short demo tailored to energy-intensive procurement "
        "is straightforward to arrange. — Manuel"
    ),
    "18": (
        "Hi — Erste Group's IT services category strategy spans seven CEE markets, each with separate "
        "procurement teams, local supplier data, and divergent market conditions. Rolling that into a "
        "coherent pan-regional strategy takes weeks and produces outputs that are partially stale on "
        "arrival. Bertelsmann used Akirolabs across 7 divisions to cut that cycle by up to 90%. "
        "I can walk through a 15-minute demo. — Manuel"
    ),
}

BEFORE_AFTER_IDS = {"1", "7", "17"}


def main():
    # Read existing CSV
    rows = []
    fieldnames = None
    before_snapshots = {}

    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        for row in reader:
            row_id = row["id"]
            if row_id in BEFORE_AFTER_IDS:
                before_snapshots[row_id] = row["linkedin_dm"]
            if row_id in NEW_DMS:
                row["linkedin_dm"] = NEW_DMS[row_id]
            rows.append(row)

    # Write back
    with open(CSV_PATH, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written {len(rows)} rows to {CSV_PATH}\n")
    print("=" * 72)

    # Print before/after for requested rows
    labels = {"1": "Row 1 — Continental AG", "7": "Row 7 — Commerzbank AG", "17": "Row 17 — Wacker Chemie AG"}
    for row_id in ("1", "7", "17"):
        print(f"\n{labels[row_id]}")
        print("-" * 72)
        print("BEFORE:")
        print(before_snapshots[row_id])
        wc_before = len(before_snapshots[row_id].split())
        print(f"  [{wc_before} words]")
        print("\nAFTER:")
        after = NEW_DMS[row_id]
        print(after)
        wc_after = len(after.split())
        print(f"  [{wc_after} words]")
        print("=" * 72)


if __name__ == "__main__":
    main()
