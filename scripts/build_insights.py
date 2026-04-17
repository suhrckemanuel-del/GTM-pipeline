import csv
from pathlib import Path

rows = [
    (1, 1, "Tier messaging may blur across customer tiers", "2-week single-tier experiment + objection log", "Faster ICP clarity before scaling spend", "med", "pipeline/value-notes/01-gleef.md"),
    (2, 2, "Enterprise buyers need productized proof not generic AI demos", "One vertical production teardown + narrow outbound", "Higher reply quality and shorter cycles", "med", "pipeline/value-notes/02-nexus.md"),
    (3, 3, "Crowded AI SDR category; buyers skeptical", "One wedge + geo public experiment narrative", "Clearer differentiation vs generic tools", "med", "pipeline/value-notes/03-enginy.md"),
    (4, 7, "AI pricing confuses CFO vs PM vs Eng", "Three-audience pricing page + example usage model", "Shorter enterprise internal alignment", "med", "pipeline/value-notes/07-paid-ai.md"),
    (5, 21, "High-ticket needs vertical trust and conversion story", "Three vertical micro-sites + vertical outbound test", "Higher intent pipeline in proven verticals", "med", "pipeline/value-notes/21-clerq.md"),
    (6, 23, "Embedded pay competitive; need ISV playbooks", "Payments revenue launch kit for top 3 ISV segments", "Faster ISV launches and partner-led growth", "med", "pipeline/value-notes/23-payabli.md"),
    (7, 24, "Agent + payments raises security/compliance questions", "VP-Product-friendly security narrative + reference flow", "Fewer security stalls in POC", "med", "pipeline/value-notes/24-basis-theory.md"),
    (8, 25, "Unified rails story can read as feature checklist", "Single corridor + ICP GTM wedge first", "Higher reply rates and cleaner feedback", "med", "pipeline/value-notes/25-onenext.md"),
    (9, 4, "Orchestration category crowded; hero story too broad", "Three workflow pattern landings + NA/EU AB test", "Better qualified demos", "med", "pipeline/value-notes/04-kestra.md"),
    (10, 26, "Inventory finance spans CFO and ops; messaging splits", "Retail vs wholesale outbound AB + ROI sketch", "Clearer ICP and faster discovery", "med", "pipeline/value-notes/26-autone.md"),
    (11, 5, "AI compute story can collapse to undifferentiated GPU rental", "Workload-split funnel + light TCO + one workload proof", "Shorter technical cycles vs cloud default", "med", "pipeline/value-notes/05-flexai.md"),
    (12, 6, "Horizontal enterprise automation attracts noisy pipeline", "One vertical flagship + ICP filter on inbound", "Higher-quality demos and faster sales learning", "med", "pipeline/value-notes/06-maisa-ai.md"),
    (13, 8, "Complex agents stall without explicit business case", "Three blueprint pilots + redacted 90-day timeline", "Faster enterprise consensus on scope and KPIs", "med", "pipeline/value-notes/08-octonomy.md"),
    (14, 9, "OSS and enterprise buyers evaluate on different criteria", "Dual front doors + 2-week evaluation kit", "Higher OSS-to-paid and shorter security reviews", "med", "pipeline/value-notes/09-cognee.md"),
    (15, 10, "PLG scale can outrun packaging and upgrade clarity", "Packaging experiment + power-user cohort upgrade story", "Cleaner ARPU and sales-assist triggers", "med", "pipeline/value-notes/10-lovable.md"),
    (16, 11, "Benchmark-led story can underweight production trust", "Versioning/SLO narrative + workload-shaped reference", "Stronger enterprise pull and fewer stability stalls", "med", "pipeline/value-notes/11-black-forest-labs.md"),
    (17, 13, "Developer vs security messaging can split the story", "Dual tracks + CISO one-pager for evidence", "Faster dual-thread deals", "med", "pipeline/value-notes/13-lakera-ai.md"),
    (18, 14, "OSS roots can blur commercial boundary vs Zapier/Make/IT build", "Segment migration guides + cloud vs self-host decision", "Higher paid conversion and less procurement thrash", "med", "pipeline/value-notes/14-n8n.md"),
    (19, 15, "Horizontal applied ML forces bespoke imagining every time", "One vertical beachhead + full GTM kit for a quarter", "Faster repeatable motion and referrals", "med", "pipeline/value-notes/15-adaptive-ml.md"),
    (20, 22, "Global FX story can feel thin in new corridors", "Corridor pages + implementation narrative + narrow outbound", "Higher intent in geography expansion", "med", "pipeline/value-notes/22-openfx.md"),
]


def main():
    root = Path(__file__).resolve().parents[1]
    path = root / "pipeline" / "insights.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "insight_id",
                "company_id",
                "observed_issue",
                "recommended_idea",
                "expected_impact",
                "confidence_low_med_high",
                "source_url",
            ]
        )
        w.writerows(rows)
    print(f"Wrote {len(rows)} insights")


if __name__ == "__main__":
    main()
