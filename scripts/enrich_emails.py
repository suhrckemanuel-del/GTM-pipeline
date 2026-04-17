"""
Fill work_email on pipeline/contacts.csv using Hunter.io Email Finder.

Requires:
  - HUNTER_API_KEY in environment (see repo .env.example)
  - pipeline/company_domains.csv with primary_domain filled for target companies
  - contact name as "First Last" (not TO_RESEARCH)

Does NOT scrape LinkedIn. See plans/email-discovery-feature.md.
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("Install dependencies: pip install -r requirements.txt", file=sys.stderr)
    raise

HUNTER_FINDER_URL = "https://api.hunter.io/v2/email-finder"


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def read_domains(root: Path) -> dict[str, str]:
    path = root / "pipeline" / "company_domains.csv"
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cid = (row.get("company_id") or "").strip()
            dom = (row.get("primary_domain") or "").strip().lower()
            if cid and dom:
                out[cid] = dom
    return out


def split_name(full: str) -> tuple[str, str] | None:
    full = full.strip()
    if not full or full.upper() == "TO_RESEARCH":
        return None
    parts = full.split(None, 1)
    if len(parts) < 2:
        return None
    return parts[0], parts[1]


def hunter_find_email(api_key: str, domain: str, first: str, last: str) -> tuple[str | None, str, int | None]:
    params = {
        "domain": domain,
        "first_name": first,
        "last_name": last,
        "api_key": api_key,
    }
    r = requests.get(HUNTER_FINDER_URL, params=params, timeout=30)
    if r.status_code == 429:
        return None, "rate_limited", None
    if r.status_code != 200:
        return None, f"http_{r.status_code}", None
    data = r.json().get("data") or {}
    email = data.get("email")
    score = data.get("score")
    if email:
        return str(email).strip().lower(), "found", int(score) if score is not None else None
    return None, "not_found", None


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_env_file(root / ".env")

    p = argparse.ArgumentParser(description="Enrich contacts.csv work emails via Hunter.io")
    p.add_argument("--dry-run", action="store_true", help="Print actions without writing CSV")
    p.add_argument("--force", action="store_true", help="Overwrite existing work_email")
    p.add_argument("--sleep", type=float, default=0.35, help="Seconds between API calls")
    args = p.parse_args()

    api_key = (os.environ.get("HUNTER_API_KEY") or "").strip()
    if not api_key and not args.dry_run:
        print("Set HUNTER_API_KEY or use --dry-run.", file=sys.stderr)
        sys.exit(1)

    domains_by_company = read_domains(root)
    contacts_path = root / "pipeline" / "contacts.csv"
    if not contacts_path.is_file():
        print("Missing pipeline/contacts.csv", file=sys.stderr)
        sys.exit(1)

    with contacts_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    required = {"company_id", "name", "work_email", "email_status", "email_source"}
    if not required.issubset(set(fieldnames)):
        print(
            "contacts.csv missing columns. Expected work_email, email_status, email_source.",
            file=sys.stderr,
        )
        sys.exit(1)

    updated = 0
    for row in rows:
        cid = str(row.get("company_id", "")).strip()
        existing = (row.get("work_email") or "").strip()
        if existing and not args.force:
            continue

        parsed = split_name(row.get("name") or "")
        if not parsed:
            row["email_status"] = row.get("email_status") or "skipped_no_real_name"
            row["email_source"] = row.get("email_source") or ""
            continue

        domain = domains_by_company.get(cid)
        if not domain:
            row["email_status"] = row.get("email_status") or "skipped_no_domain"
            row["email_source"] = row.get("email_source") or ""
            continue

        first, last = parsed
        if args.dry_run:
            print(f"[dry-run] company_id={cid} domain={domain} name={first} {last}")
            continue

        email, status, _score = hunter_find_email(api_key, domain, first, last)
        time.sleep(max(args.sleep, 0))

        if email:
            row["work_email"] = email
            row["email_status"] = "found"
            row["email_source"] = "hunter_email_finder"
            updated += 1
        else:
            row["work_email"] = ""
            row["email_status"] = status
            row["email_source"] = "hunter_email_finder" if status != "rate_limited" else ""

    if args.dry_run:
        print("--dry-run: no file written.")
        return

    with contacts_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {contacts_path}; filled {updated} work_email field(s).")


if __name__ == "__main__":
    main()
