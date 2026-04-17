const companies = [
    { name: "Gleef", stage: "Growth (15–40)", vertical: "AI", hook: "Ongoing B2B SaaS GTM project; Paris", status: "qual" },
    { name: "Nexus", stage: "Seed (15–35)", vertical: "AI", hook: "€3.7M seed Apr 2026; YC + General Catalyst", status: "qual" },
    { name: "Enginy", stage: "Seed (20–40)", vertical: "AI", hook: "€5M seed Jan 2026; EU + US expansion push", status: "qual" },
    { name: "Kestra", stage: "Series A (80–150)", vertical: "AI", hook: "€21M Series A Mar 2026; Kestra 2.0 + cloud + NA/EU GTM", status: "qual" },
    { name: "FlexAI", stage: "Seed (40–80)", vertical: "AI", hook: "€28.5M seed; Sifted Rising 100 2025", status: "qual" },
    { name: "Maisa AI", stage: "Seed (40–100)", vertical: "AI", hook: "$25M seed 2025; enterprise automation scale", status: "qual" },
    { name: "Paid.ai", stage: "Seed (30–70)", vertical: "AI", hook: "€21M seed 2025; revenue engine for AI agents", status: "qual" },
    { name: "Octonomy", stage: "Seed (30–60)", vertical: "AI", hook: "~$20M seed 2025; enterprise GTM push", status: "qual" },
    { name: "Cognee", stage: "Seed (25–50)", vertical: "AI", hook: "€7.5M 2026 press cluster; AI memory + OSS → enterprise", status: "qual" },
    { name: "Lovable", stage: "Seed (50–120)", vertical: "AI", hook: "€14.6M+ seed (Sifted 2025); PLG + community motion", status: "qual" },
    { name: "Black Forest Labs", stage: "Seed (40–100)", vertical: "AI", hook: "€28.2M seed (Sifted 2025); API + enterprise interest", status: "qual" },
    { name: "Weaviate", stage: "Series C (100+)", vertical: "AI", hook: "Vector DB category scale; cloud + enterprise", status: "qual" },
    { name: "Lakera AI", stage: "Series A (40–80)", vertical: "AI", hook: "€18.2M Series A; LLM security dual buyer path", status: "qual" },
    { name: "n8n", stage: "Series B (150+)", vertical: "AI", hook: "Workflow automation + AI features; OSS + enterprise", status: "qual" },
    { name: "Adaptive ML", stage: "Seed (20–45)", vertical: "AI", hook: "Seed (Sifted Rising 2025); applied ML GTM", status: "qual" },
    { name: "Qdrant", stage: "Series A (60–100)", vertical: "AI", hook: "€25.7M Series A; vector growth + cloud revenue", status: "qual" },
    { name: "Appwrite", stage: "Series A (80–120)", vertical: "AI", hook: "€24.6M Series A; developer platform expansion", status: "qual" },
    { name: "Morpho", stage: "Growth (30–70)", vertical: "AI", hook: "Paris AI research/product momentum", status: "qual" },
    { name: "Rapidata", stage: "Seed (15–35)", vertical: "AI", hook: "€7.2M cluster; data for AI training + evaluation", status: "qual" },
    { name: "Elyos AI", stage: "Seed (20–45)", vertical: "AI", hook: "€11.1M; customer-facing workflow automation", status: "qual" },
    { name: "Clerq", stage: "Series A (40–90)", vertical: "Fintech", hook: "$21M Oct 2025; 6× revenue growth cited", status: "qual" },
    { name: "OpenFX", stage: "Series A (50–120)", vertical: "Fintech", hook: "$94M Series A Mar 2026; SEA expansion + hiring", status: "qual" },
    { name: "Payabli", stage: "Series B (80–150)", vertical: "Fintech", hook: "$28M Series B Jun 2025; embedded payfac for vertical SaaS", status: "qual" },
    { name: "Basis Theory", stage: "Series B (35–55)", vertical: "Fintech", hook: "$33M Series B Oct 2025; agentic commerce wedge", status: "qual" },
    { name: "OneNext", stage: "Seed (25–55)", vertical: "Fintech", hook: "$5.5M seed Jan 2025; Citi Ventures backing", status: "qual" },
    { name: "autone", stage: "Series A (40–80)", vertical: "Fintech", hook: "€15.4M Series A (Sifted); inventory + cash flow", status: "qual" },
    { name: "Pennylane", stage: "Series C (400+)", vertical: "Fintech", hook: "SMB accounting platform; mid-market EU GTM", status: "qual" },
    { name: "Agicap", stage: "Series C (300+)", vertical: "Fintech", hook: "Cash flow management; EU expansion", status: "qual" },
    { name: "Pleo", stage: "Series C (500+)", vertical: "Fintech", hook: "Spend management scale; enterprise + SMB motion", status: "qual" },
    { name: "Spendesk", stage: "Series C (500+)", vertical: "Fintech", hook: "Spend management; EU GTM scale", status: "qual" },
    { name: "Upvest", stage: "Series B (100+)", vertical: "Fintech", hook: "Investment API infra; partnerships motion", status: "qual" },
    { name: "Swan", stage: "Series B (100+)", vertical: "Fintech", hook: "Banking-as-a-service; partner-led GTM", status: "qual" },
    { name: "Moss", stage: "Series B (150+)", vertical: "Fintech", hook: "Spend management DACH; GTM scale push", status: "qual" },
    { name: "Primer", stage: "Series B (80–140)", vertical: "Fintech", hook: "Payments orchestration; global merchants", status: "qual" },
    { name: "Billie", stage: "Series C (200+)", vertical: "Fintech", hook: "B2B BNPL scale; merchant acquisition", status: "qual" },
    { name: "PayFit", stage: "Series D (700+)", vertical: "Fintech", hook: "Payroll + HR at scale across EU", status: "qual" },
    { name: "Column", stage: "Series C (100+)", vertical: "Fintech", hook: "Banking API; developer-first GTM", status: "qual" },
    { name: "Modern Treasury", stage: "Series C (150+)", vertical: "Fintech", hook: "Payment operations; enterprise GTM", status: "qual" },
    { name: "Tesseract", stage: "Growth (40–100)", vertical: "Fintech", hook: "Trading/infra; institutional GTM wedge", status: "qual" },
    { name: "Arc", stage: "Series A/B (40–90)", vertical: "Fintech", hook: "Startup banking stack; GTM scale motion", status: "qual" },
    { name: "akirolabs", stage: "Series A (30–80)", vertical: "AI", hook: "AI-powered procurement strategy; BDR GTM build", status: "qual" },
    { name: "Dust", stage: "Seed (10–25)", vertical: "AI", hook: "$5M seed 2023; enterprise AI assistant pilots growing", status: "qual" },
    { name: "Nabla", stage: "Series A (40–80)", vertical: "AI", hook: "$24M Series A 2023; US healthcare expansion", status: "qual" },
    { name: "Holistic AI", stage: "Series A (30–60)", vertical: "AI", hook: "$8.5M Series A; EU AI Act tailwinds + FT coverage", status: "qual" },
    { name: "Unstructured", stage: "Series A (30–60)", vertical: "AI", hook: "$40M Series A 2023; OSS adoption + enterprise upsell", status: "qual" },
    { name: "Arize AI", stage: "Series B (50–80)", vertical: "AI", hook: "$38M Series B 2023; LLM observability demand surge", status: "qual" },
    { name: "Sardine", stage: "Series B (50–80)", vertical: "Fintech", hook: "$51.5M Series B 2023; fraud + compliance growth", status: "qual" },
    { name: "Numeral", stage: "Seed (15–35)", vertical: "Fintech", hook: "€7M seed; European bank payment infrastructure API", status: "qual" },
    { name: "Defacto", stage: "Series A (30–60)", vertical: "Fintech", hook: "€15M Series A; embedded B2B BNPL for marketplaces", status: "qual" },
    { name: "Karmen", stage: "Series A (20–45)", vertical: "Fintech", hook: "€55M total; revenue-based financing for EU SaaS", status: "qual" },
];

const valueNotes = [
    {
        company: "FlexAI",
        vertical: "AI / Compute Infrastructure",
        observation: "Infrastructure buyers compare you to hyperscalers using price per GPU-hour before they understand workload fit. If the homepage leads with generic 'AI compute,' prospects mentally bucket you as undifferentiated silicon rental.",
        suggestion: "Split the top of funnel into two crisp paths—training and inference—with one diagram each and a light TCO framing (3 inputs, one scenario). Pair with one public benchmark or customer-shaped story that names the workload pattern.",
        impact: "Shorter technical discovery calls and fewer 'we'll stay on the cloud for now' stalls because buyers see their problem reflected before the price conversation."
    },
    {
        company: "Maisa AI",
        vertical: "AI / Enterprise Automation",
        observation: "'Enterprise workflow automation' is a wide aperture: RevOps, finance ops, and IT automation buyers all show up with different success metrics. When the hero story stays horizontal, outbound and demos attract a mix of low-intent testers and the pipeline gets noisy.",
        suggestion: "Pick one flagship vertical for 6–8 weeks and make it explicit on the homepage hero, paid landing, and first case study: named workflows, before/after time-to-complete, and who owns the bot. Run a simple ICP filter on inbound before booking demos.",
        impact: "Higher-quality pipeline and faster sales cycles because prospects self-identify—or disqualify—before the first call."
    },
    {
        company: "Octonomy",
        vertical: "AI / Enterprise Automation Agents",
        observation: "Enterprise buyers tolerate pilots when the business case is explicit—who saves time, what breaks if the agent is wrong, and how you measure success in 90 days. When the story stays 'intelligent automation,' procurement and business sponsors struggle to align with IT/security on scope.",
        suggestion: "Package three repeatable use-case blueprints (industry or function-specific) each with: trigger → agent steps → human review gates → KPIs. Publish one redacted pilot timeline (week-by-week) so champions can paste it into internal memos.",
        impact: "Faster consensus across business and technical stakeholders and fewer stalled POCs waiting for a bespoke success definition."
    },
    {
        company: "Cognee",
        vertical: "AI / Memory & Knowledge Infrastructure",
        observation: "Projects that grow from OSS attract developers first while revenue needs platform and security buyers. If both audiences see the same narrative—generic 'memory layer'—enterprise deals stall on governance, data residency, and evaluation criteria that OSS users rarely ask upfront.",
        suggestion: "Create two front doors: a developer path (quickstarts, benchmarks, integrations) and an enterprise path (memory guarantees, access control model, audit story). Add one 'evaluation kit' page: what to test in 2 weeks, what logs to inspect, and what 'good' looks like.",
        impact: "Higher OSS-to-paid conversion and shorter enterprise security reviews because evaluation expectations are explicit."
    },
    {
        company: "Lovable",
        vertical: "AI / Product Creation (PLG)",
        observation: "Viral PLG can scale usage faster than pricing and packaging clarity. Teams, agencies, and indie hackers often share the same top-of-funnel story, which makes it harder to tune upgrade triggers and sales-assist plays without feeling like you're 'taxing' the community.",
        suggestion: "Run a packaging experiment on the upgrade path: separate 'solo builder' vs 'team shipping to customers' with one measurable outcome each. Pair with a cohort-based message to power users (templates, collaboration, brand controls) instead of a one-size upgrade modal.",
        impact: "Cleaner revenue per active user and a clearer story for when sales-assist should engage vs stay self-serve."
    },
    {
        company: "Black Forest Labs",
        vertical: "AI / Foundation Models",
        observation: "Model providers often compete on leaderboard scores while enterprise buyers optimize for reliability, change management, and support when models ship breaking updates. If marketing is benchmark-forward only, CTOs hear 'research pace risk' louder than 'production partner.'",
        suggestion: "Publish a production readiness narrative: versioning policy, deprecation notice windows, latency/SLO framing for API tiers, and a short migration guide when families update. Pair with one vertical or workload reference anchored in customer-shaped language.",
        impact: "Stronger enterprise pull-in and fewer eval cycles lost to 'we'll wait for stability' objections."
    },
    {
        company: "Lakera AI",
        vertical: "AI / LLM Security",
        observation: "Security products that also sell to developers can split messaging: engineering wants SDKs and fast tests; security wants governance, reporting, and procurement-ready assurances. If both are blended on one page, each side sees half a product.",
        suggestion: "Maintain dual tracks with a shared backbone story: developer path (integrations, CI hooks, quick eval) and security path (policy, dashboards, evidence for risk reviews). Add a one-page 'bring your CISO' summary: what you log, what you block, what artifacts export for audits.",
        impact: "Faster dual-thread deals (Eng + Security) and fewer lost cycles from 'cool demo, unclear enterprise fit.'"
    },
    {
        company: "n8n",
        vertical: "AI / Workflow Automation",
        observation: "Strong OSS communities often stall commercial growth when the upgrade path feels fuzzy: self-hosted vs cloud, which seats matter, and what 'enterprise' unlocks beyond hosting. Buyers compare you to Zapier/Make and to internal IT build-vs-buy.",
        suggestion: "Ship named migration and packaging stories by segment: agencies (multi-client workspaces), mid-market IT (SSO, environments, approvals), and enterprise (audit, SLAs). Add a simple decision guide ('choose cloud if… choose self-host if…').",
        impact: "Higher conversion from free/active users to paid plans and shorter enterprise procurement because the commercial boundary is explicit."
    },
    {
        company: "Adaptive ML",
        vertical: "AI / Applied ML",
        observation: "Horizontal 'applied ML' positioning forces every prospect to imagine the product in their context from scratch. In crowded markets, the winners usually repeat one vertical depth story until outbound and inbound rhyme—same vocabulary, same metrics, same proof artifacts.",
        suggestion: "Pick one vertical beachhead and build a full-stack GTM kit: landing section, 2 customer-shaped examples, objection FAQ, and one outbound hook tied to a measurable KPI (yield, churn, margin). Say no to everything else in hero copy for one quarter.",
        impact: "Faster sales learning loops and clearer referrals because customers recognize 'people like us' immediately."
    },
    {
        company: "OpenFX",
        vertical: "Fintech / FX & Liquidity",
        observation: "FX and liquidity platforms win on trust, depth, and corridor-specific behavior as much as API ergonomics. When growth pushes into new regions, buyers ask different questions about regulation, settlement, and local rails—a single global story can feel thin next to incumbents with local proof.",
        suggestion: "For the next geography push, ship corridor-specific pages (route, use cases, compliance transparency, what 'good' latency looks like) plus one implementation narrative. Pair with narrow outbound: teams already shipping volume in that corridor.",
        impact: "Higher intent conversations in new markets and fewer eval cycles lost to 'we need someone who has done this here before.'"
    },
    {
        company: "akirolabs",
        vertical: "AI / Procurement Strategy",
        observation: "Procurement strategy AI sits between spend management tools (Coupa, Ariba) and strategic sourcing consultants (McKinsey, PWC). Enterprise buyers default to 'what's different about you?' The risk is being filed as 'another procurement tool' before the conversation starts.",
        suggestion: "Lead with one strategic decision, one before/after. Pick the procurement scenario where the status quo is most painful and build a one-page 'without akirolabs / with akirolabs' for that scenario only. Use that single story for outbound until it converts, then expand.",
        impact: "Fewer 'we already have Coupa' deflections and shorter discovery calls because the buyer walks in knowing which problem akirolabs solves—not having to figure it out during the demo."
    }
];

// Populate Company Research Table
function populateCompanies() {
    const tbody = document.getElementById('company-table-body');
    if (!tbody) return;

    tbody.innerHTML = '';
    companies.forEach(c => {
        const verticalClass = c.vertical === 'AI' ? 'tag-blue' : 'tag-purple';
        const statusHtml = '<span class="status-indicator"><span class="status-dot green"></span> Qualified</span>';

        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><strong>${c.name}</strong> <span class="tag ${verticalClass} tag-sm">${c.vertical}</span></td>
            <td>${c.stage}</td>
            <td>${c.hook}</td>
            <td>${statusHtml}</td>
        `;
        tbody.appendChild(tr);
    });
}

// Populate Value Notes
function populateValueNotes() {
    const container = document.getElementById('value-notes-carousel');
    if (!container) return;

    container.innerHTML = '';
    valueNotes.forEach(vn => {
        const card = document.createElement('div');
        card.className = 'glass-card';
        card.innerHTML = `
            <div class="card-header">
                <h3>${vn.company}</h3>
                <span class="tag tag-gray">${vn.vertical}</span>
            </div>
            <div class="vn-section">
                <h4>Observation</h4>
                <p>"${vn.observation}"</p>
            </div>
            <div class="vn-section">
                <h4>Suggestion</h4>
                <p>${vn.suggestion}</p>
            </div>
            <div class="vn-section">
                <h4>Expected Impact</h4>
                <p>${vn.impact}</p>
            </div>
        `;
        container.appendChild(card);
    });
}

// Navigation Logic
function setupNavigation() {
    const sections = document.querySelectorAll('.dashboard-section');

    function setActive(targetId) {
        document.querySelectorAll('.nav-links a').forEach(l => l.classList.remove('active'));
        const activeLink = document.querySelector(`.nav-links a[href="#${targetId}"]`);
        if (activeLink) activeLink.classList.add('active');

        sections.forEach(s => {
            s.classList.remove('active');
            s.classList.add('hidden');
        });

        const activeSection = document.getElementById(targetId);
        if (activeSection) {
            activeSection.classList.remove('hidden');
            activeSection.classList.add('active');
        }
    }

    document.querySelectorAll('.nav-links a').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = link.getAttribute('href').substring(1);
            setActive(targetId);
        });
    });
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    populateCompanies();
    populateValueNotes();
    setupNavigation();
});
