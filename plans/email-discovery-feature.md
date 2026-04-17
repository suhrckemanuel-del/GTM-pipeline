# Email discovery & enrichment — product plan

## Goal

Fill **work emails** (and status/source metadata) for rows in `pipeline/contacts.csv`, using **compliant, maintainable** methods—not brittle “scrape everything” automation that breaks ToS or privacy law.

## What we are **not** building (and why)

| Approach | Why skip (or deprioritize) |
|----------|----------------------------|
| **Scraping LinkedIn** for emails | Violates LinkedIn ToS; high ban risk; legally sensitive for EU cold outreach (GDPR legitimate interest still needs care, and scraped data is a red flag). |
| **Buying bulk “email lists”** | Quality and consent issues; damages deliverability and reputation. |
| **Aggressive site crawling** | Many sites forbid it in `robots.txt`/ToS; easy to get blocked; often yields `info@` only. |

## Recommended architecture (phased)

### Phase 0 — Data model (done in repo)

- `contacts.csv` gains: `work_email`, `email_status`, `email_source`.
- `company_domains.csv`: `company_id`, `primary_domain` (you maintain; required for domain-based APIs).
- Regenerating contacts from `build_contacts_outreach.py` **preserves** email fields when `company_id` + `role` match.

### Phase 1 — **Enrichment APIs** (primary)

Use a commercial **email finder / domain search** API with clear licensing:

- **[Hunter.io](https://hunter.io)** — Domain search + email finder (implemented in `scripts/enrich_emails.py` as the first provider).
- Alternatives to add later: **Apollo**, **Clearbit**, **Dropcontact**, **Lusha** (each needs its own adapter and your API key).

**Flow**

1. You fill `primary_domain` per company (e.g. `kestra.io`) in `pipeline/company_domains.csv`.
2. You replace `TO_RESEARCH` with a real person name (`First Last`) and optionally `profile_url` in `contacts.csv`.
3. Run `python scripts/enrich_emails.py` (with `HUNTER_API_KEY` in `.env`).
4. Script sets `work_email`, `email_status` (`found` / `not_found` / `ambiguous` / `skipped_*`), `email_source` (`hunter_email_finder`).

**Limits**

- APIs cost credits and rate-limit; the script supports `--dry-run` and skips rows that already have an email unless `--force`.

### Phase 2 — **Optional public-page harvest** (strictly limited)

If you still want “scraping,” keep it narrow:

- Only fetch **one or two allow-listed paths** per domain (e.g. `/contact`, `/legal`, team page) with `requests`, **respect `robots.txt`**, conservative rate limits, and **no** login walls.
- Extract `mailto:` and visible text emails; mark `email_source=website_public` and `email_status=needs_manual_verify`.

This is **optional** and behind a flag (e.g. `--harvest-public-mailto`) so default behavior stays API-based.

### Phase 3 — **CRM sync (Notion MCP)**

Notion MCP can **update** pages/databases once you have a database and property mapping. It does not replace a paid enrichment API for discovery.

- You create a Notion DB (or use an existing one) with properties: Company, Contact name, Email, Status, LinkedIn URL, etc.
- Phase 3 work: small script or manual Zapier/Make, or a future `scripts/sync_to_notion.py` that reads `contacts.csv` and calls Notion APIs (or uses MCP from Cursor interactively).

**From you:** Notion database ID, property names, and confirmation you want one-way sync (CSV → Notion) or two-way.

## What I need from you (checklist)

1. **Chosen provider** — Confirm Hunter is OK, or name the vendor you already pay for (we add an adapter).
2. **API key** — Put it in `.env` as `HUNTER_API_KEY=...` (file is gitignored). Never commit keys.
3. **`company_domains.csv`** — Fill `primary_domain` for each company you will enrich (start with batch-01 `company_id`s).
4. **Contact names** — Replace `TO_RESEARCH` with `First Last` for rows you want the finder to run on.
5. **Compliance stance** — Confirm you are OK with **cold B2B outreach** under your jurisdiction’s rules (e.g. GDPR legitimate interest assessment for EU contacts, CAN-SPAM/CASL where relevant). This is **legal advice you confirm with counsel**, not something the repo encodes.
6. **If you want Phase 3 (Notion)** — Database URL or ID + field map.

## Success metrics

- % of batch-01 contacts with `work_email` and `email_status=found`.
- Bounce rate after verification (consider a verifier step in a later iteration).
- Time saved vs fully manual lookup.

## Immediate next engineering tasks

- [x] Schema: `work_email`, `email_status`, `email_source` on contacts; `company_domains.csv`; merge-safe `build_contacts_outreach.py`.
- [x] `scripts/enrich_emails.py` with Hunter email-finder + `--dry-run`.
- [ ] Optional: second provider adapter (Apollo, etc.).
- [ ] Optional: `--harvest-public-mailto` with robots.txt check.
- [ ] Optional: Notion sync script + MCP-assisted setup doc.
