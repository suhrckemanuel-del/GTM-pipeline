import argparse
import csv
from pathlib import Path

rows = [
    (1, "Gleef", "AI", "EU-France", "Growth", "15-40", "Ongoing GTM strategy project (AMSA); B2B SaaS Paris", "Possible via relationship", "YES", "Warm: active project; founders reachable", 1, "Prioritize founder + commercial lead"),
    (2, "Nexus", "AI", "EU-Belgium", "Seed", "15-35", "Seed ~EUR3.7M Apr 2026; YC + General Catalyst", "Scale platform + enterprise adoption", "YES", "Agents for non-technical teams; implementation-led GTM", 1, ""),
    (3, "Enginy", "AI", "EU-Spain", "Seed", "20-40", "EUR5M seed Jan 2026; US UK DE FR IT NL expansion", "Hiring; scale internationally", "YES", "AI outbound/SDR wedge", 1, ""),
    (4, "Kestra", "AI", "EU-France", "Series A", "80-150", "Series A EUR21M Mar 2026; Kestra 2.0 + cloud + GTM NA/EU", "Enterprise sales + marketing", "YES", "Orchestration category; positioning + enterprise use cases", 2, "Larger team"),
    (5, "FlexAI", "AI", "EU-France", "Seed", "40-80", "Large seed EUR28.5M (Sifted Rising 100 2025)", "Scale AI compute product", "YES", "Technical buyer education GTM", 2, ""),
    (6, "Maisa AI", "AI", "EU-Spain", "Seed", "40-100", "USD25M seed 2025 (Tech.eu); enterprise automation", "Scale team + self-serve", "YES", "Enterprise workflow automation ICP", 2, ""),
    (7, "Paid.ai", "AI", "EU-UK", "Seed", "30-70", "EUR21M seed 2025; revenue engine for AI agents", "Partnerships + category", "YES", "Usage-based billing narrative for agents", 1, ""),
    (8, "Octonomy", "AI", "EU-Germany", "Seed", "30-60", "~USD20M seed 2025 (major seed lists)", "Enterprise GTM", "YES", "Complex automation agents ROI story", 2, ""),
    (9, "Cognee", "AI", "EU-Germany", "Seed", "25-50", "EUR7.5M 2026 (industry press cluster); AI memory", "Enterprise adoption", "YES", "OSS/enterprise bridge GTM", 2, ""),
    (10, "Lovable", "AI", "EU-Sweden", "Seed", "50-120", "EUR14.6M+ seed (Sifted 2025)", "PLG + community", "YES", "Monetization + ICP focus", 2, ""),
    (11, "Black Forest Labs", "AI", "EU-Germany", "Seed", "40-100", "EUR28.2M seed (Sifted 2025)", "API + enterprise", "YES", "Model distribution and enterprise sales", 3, ""),
    (12, "Weaviate", "AI", "EU-Netherlands", "Series C", "100+", "Vector DB category scale", "Enterprise + cloud", "YES", "Differentiation vs hyperscalers", 3, "More mature"),
    (13, "Lakera AI", "AI", "EU-Switzerland", "Series A", "40-80", "EUR18.2M Series A (Sifted)", "LLM security GTM", "YES", "Security buyer + developer paths", 2, ""),
    (14, "n8n", "AI", "EU-Germany", "Series B", "150+", "Workflow automation; AI features", "Enterprise + self-serve", "YES", "OSS to commercial conversion", 3, "Larger org"),
    (15, "Adaptive ML", "AI", "EU-France", "Seed", "20-45", "Seed (Sifted Rising 2025)", "Applied ML GTM", "YES", "Vertical application clarity", 3, ""),
    (16, "Qdrant", "AI", "EU-Germany", "Series A", "60-100", "EUR25.7M Series A (Sifted)", "Vector growth", "YES", "Community to cloud revenue", 3, ""),
    (17, "Appwrite", "AI", "IL-Israel", "Series A", "80-120", "EUR24.6M Series A (Sifted)", "Dev platform expansion", "YES", "Developer marketing + enterprise", 3, "Non-EU/US core"),
    (18, "Morpho", "AI", "EU-France", "Growth", "30-70", "Paris AI research/product (verify latest)", "Product-led growth", "YES", "Research productization GTM", 4, "Verify funding before send"),
    (19, "Rapidata", "AI", "EU", "Seed", "15-35", "EUR7.2M cluster; data for AI (press)", "Enterprise pilots", "YES", "Data/eval buyer GTM", 4, ""),
    (20, "Elyos AI", "AI", "EU", "Seed", "20-45", "EUR11.1M (press cluster); customer workflows", "Scale GTM", "YES", "Customer-facing automation", 4, ""),
    (21, "Clerq", "Fintech", "US-NYC", "Series A", "40-90", "USD21M Oct 2025; 6x revenue growth cited", "Product + vertical expansion", "YES", "High-ticket vertical landing pages", 1, ""),
    (22, "OpenFX", "Fintech", "US", "Series A", "50-120", "USD94M Series A Mar 2026; volume growth cited", "SEA expansion + hiring", "YES", "Corridor + liquidity narrative", 2, "Very well-funded"),
    (23, "Payabli", "Fintech", "US-Miami", "Series B", "80-150", "USD28M Series B Jun 2025; USD60M total", "Hiring GTM eng product", "YES", "Embedded payfac for vertical SaaS", 1, ""),
    (24, "Basis Theory", "Fintech", "US", "Series B", "35-55", "USD33M Series B Oct 2025; agentic commerce", "Expand GTM", "YES", "Vault + agentic commerce wedge", 1, ""),
    (25, "OneNext", "Fintech", "US", "Seed", "25-55", "USD5.5M seed Jan 2025; Citi Ventures", "GTM cities + compliance", "YES", "Unified B2B payments story", 1, ""),
    (26, "autone", "Fintech", "EU-UK", "Series A", "40-80", "EUR15.4M Series A (Sifted); inventory/cash", "Scale UK/EU", "YES", "Working capital + retail vertical", 2, ""),
    (27, "Pennylane", "Fintech", "EU-France", "Series C", "400+", "SMB accounting platform scale", "Mid-market GTM", "YES", "Segment-specific campaigns FR/EU", 3, "Large"),
    (28, "Agicap", "Fintech", "EU-France", "Series C", "300+", "Cash flow management scale", "EU expansion", "YES", "Vertical ICP for forecasting", 3, ""),
    (29, "Pleo", "Fintech", "EU-Denmark", "Series C", "500+", "Spend management scale", "Enterprise + SMB", "YES", "Upmarket motion experiments", 3, ""),
    (30, "Spendesk", "Fintech", "EU-France", "Series C", "500+", "Spend management", "EU GTM", "YES", "Multi-entity finance teams", 3, ""),
    (31, "Upvest", "Fintech", "EU-Germany", "Series B", "100+", "Investment API infra", "Partnerships", "YES", "Embedded investing distribution", 3, ""),
    (32, "Swan", "Fintech", "EU-France", "Series B", "100+", "Banking-as-a-service", "Partner GTM", "YES", "Embedded finance ICP clarity", 3, ""),
    (33, "Moss", "Fintech", "EU-Germany", "Series B", "150+", "Spend management DACH", "GTM scale", "YES", "SMB vs mid-market focus tests", 3, ""),
    (34, "Primer", "Fintech", "EU-UK", "Series B", "80-140", "Payments orchestration", "Global merchants", "YES", "Orchestration vs Stripe narrative", 3, ""),
    (35, "Billie", "Fintech", "EU-Germany", "Series C", "200+", "B2B BNPL", "Merchant acquisition", "YES", "BNPL vs net terms messaging", 3, ""),
    (36, "PayFit", "Fintech", "EU-France", "Series D", "700+", "Payroll + HR", "Scale", "YES", "Payroll + embedded finance bundle", 4, "Very large"),
    (37, "Column", "Fintech", "US", "Series C", "100+", "Banking API", "Developer GTM", "YES", "Regulated infra narrative", 3, ""),
    (38, "Modern Treasury", "Fintech", "US", "Series C", "150+", "Payment operations", "Enterprise GTM", "YES", "Complex money movement ICP", 3, ""),
    (39, "Tesseract", "Fintech", "EU-UK", "Growth", "40-100", "Trading/infra (verify before outreach)", "Institutional GTM", "YES", "Institutional wedge", 4, "Verify"),
    (40, "Arc", "Fintech", "US", "Series A/B", "40-90", "Startup banking stack", "GTM scale", "YES", "Startup vs SMB ICP angle", 4, ""),
]

FIELDNAMES = [
    "company_id",
    "name",
    "vertical",
    "geography",
    "stage",
    "headcount_estimate",
    "recent_growth_signals",
    "hiring_signals",
    "checklist_pass",
    "must_haves_notes",
    "priority",
    "notes",
]


def main():
    parser = argparse.ArgumentParser(description="Build or extend companies.csv")
    parser.add_argument(
        "--append",
        metavar="CSV_FILE",
        help="Append approved candidates from this CSV to companies.csv (assigns new IDs)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    path = root / "pipeline" / "companies.csv"

    if args.append:
        # Read existing file to find max company_id
        if not path.is_file():
            print(f"Error: {path} not found. Run without --append first.", flush=True)
            return
        with path.open(encoding="utf-8-sig") as f:
            existing = list(csv.DictReader(f))
        max_id = max((int(r["company_id"]) for r in existing), default=0)

        # Read candidates file
        src = Path(args.append)
        if not src.is_file():
            print(f"Error: {src} not found.")
            return
        with src.open(encoding="utf-8-sig") as f:
            candidates = list(csv.DictReader(f))

        # Assign sequential IDs and append
        existing_names = {r["name"].strip().lower() for r in existing}
        added = 0
        with path.open("a", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
            for candidate in candidates:
                if candidate["name"].strip().lower() in existing_names:
                    print(f"  Skipping duplicate: {candidate['name']}")
                    continue
                max_id += 1
                candidate["company_id"] = max_id
                w.writerow(candidate)
                existing_names.add(candidate["name"].strip().lower())
                added += 1

        print(f"Appended {added} new companies to {path} (IDs {max_id - added + 1}–{max_id})")
        return

    # Default: rebuild from scratch
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(FIELDNAMES)
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows to {path}")


if __name__ == "__main__":
    main()
