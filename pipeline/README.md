# Pipeline (local CRM)

CSV files mirror the plan’s four entities. Edit in Excel / Google Sheets or here in Cursor.

| File | Purpose |
|------|---------|
| `companies.csv` | 40 qualified targets (20 AI, 20 fintech, EU + US mix) |
| `contacts.csv` | 30 rows = top 10 companies × ~3 roles; fill `name` + `profile_url` |
| `insights.csv` | One row per value note (top 10); `source_url` points to markdown note path |
| `outreach.csv` | One row per contact for batch 1; planned dates + status |

**Value notes (full text):** `pipeline/value-notes/*.md`

**Regenerate companies from script:** `python scripts/build_companies.py` (overwrites `companies.csv`).

**Regenerate contacts + outreach:** `python scripts/build_contacts_outreach.py` (overwrites those CSVs — only if you need to reset batch 1).
