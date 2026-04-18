from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "pipeline" / "akirolabs" / "insights.csv"

REPLACEMENTS = {
    "Ã¢â‚¬â€": "-",
    "Ã¢â‚¬â€œ": "-",
    "Ã¢â‚¬Ëœ": "'",
    "Ã¢â‚¬â„¢": "'",
    'Ã¢â‚¬Å“': '"',
    'Ã¢â‚¬\x9d': '"',
    "ÃƒÂ¼": "u",
    "ÃƒÂ¶": "o",
    "ÃƒÂ¤": "a",
    "ÃƒÅ¸": "ss",
    "akirolabs": "Akirolabs",
}

ANGLE1_PROOFS = [
    "Bertelsmann used Akirolabs across 7 divisions and cut strategy refresh time by up to 90%.",
    "At Bertelsmann, Akirolabs moved category strategy work across 7 divisions from weeks to days.",
    "Bertelsmann used Akirolabs to compress multi-division strategy refreshes into a days-long workflow.",
]

ANGLE2_PROOFS = [
    "Merck uses Akirolabs as the strategy layer above its existing procurement stack, so the suite stays in place.",
    "Merck and Axpo run Akirolabs on top of the execution stack they already own, with no replacement project attached.",
    "At Merck, Akirolabs handles the strategy work before decisions flow into the downstream procurement tools.",
]

ANGLE3_PROOFS = [
    "Raiffeisen Bank used Akirolabs to bring neglected categories under formal strategy without adding headcount.",
    "Raiffeisen Bank used Akirolabs to move autopilot categories back under documented strategy and expand coverage.",
    "Raiffeisen Bank used Akirolabs to increase spend under strategy across categories that had been running on inertia.",
]

DM_OFFERS = {
    1: [
        "I can map that workflow to {company}.",
        "I can show where that fits {company}.",
        "I can send the workflow for {company}.",
    ],
    2: [
        "I can show where that fits {company}'s stack.",
        "I can map that setup to {company}.",
        "I can share where that layer fits at {company}.",
    ],
    3: [
        "I can share the benchmark for {industry}.",
        "I can send the benchmark and first gaps.",
        "I can share where teams usually start.",
    ],
}


def clean_text(text: str) -> str:
    cleaned = text or ""
    for bad, good in REPLACEMENTS.items():
        cleaned = cleaned.replace(bad, good)
    cleaned = cleaned.replace("—", ", ")
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = re.sub(r"\s+([,.;:?!])", r"\1", cleaned)
    return cleaned.strip()


def normalize_clause(text: str) -> str:
    clause = clean_text(text).rstrip(".")
    clause = re.sub(r"^\s*Before:\s*", "", clause, flags=re.I)
    clause = re.sub(r"^\s*Today,?\s*", "", clause, flags=re.I)
    return clause


def pain_core(row: dict, max_words: int = 10) -> str:
    clause = normalize_clause(row["pain_signal"]).lower()
    clause = clause.replace(row["company"].lower(), "the company")
    return trim_words(clause, max_words).rstrip(".")


def trim_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    trimmed = " ".join(words[:max_words]).rstrip(" ,;:")
    if trimmed and trimmed[-1] not in ".!":
        trimmed += "."
    return trimmed


def paragraph_from_before_after(row: dict) -> str:
    before = clean_text(row.get("before_after", ""))
    if "With Akirolabs:" in before:
        before = before.split("With Akirolabs:", 1)[0]
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", before) if s.strip()]
    if not sentences:
        return normalize_clause(row.get("pain_signal", ""))
    return " ".join(sentences[:2]).strip()


def angle1_observation(row: dict) -> str:
    clause = pain_core(row)
    return (
        f"{row['company']} is under pressure to refresh category strategy faster as {clause}."
    )


def angle2_observation(row: dict) -> str:
    clause = pain_core(row)
    return (
        f"{row['company']}'s procurement team likely has execution tooling in place, but {clause} still has to be turned into strategy before sourcing starts."
    )


def angle3_observation(row: dict) -> str:
    base = paragraph_from_before_after(row)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", base) if s.strip()]
    if sentences:
        first = re.sub(r"^\s*Before:\s*", "", sentences[0], flags=re.I)
        return trim_words(first, 22)
    return (
        f"{row['company']} likely has indirect categories running without a current strategy as {pain_core(row)}."
    )


def offer_text(row: dict, angle: int, variant: int) -> str:
    company = row["company"]
    industry = row["industry"]
    if angle == 1:
        offers = [
            f"I can walk through the Bertelsmann workflow and map it to {company}.",
            f"I can share the operating model behind Bertelsmann's rollout and where it fits {company}.",
            f"I can send the Bertelsmann workflow and show where it would apply at {company}.",
        ]
    elif angle == 2:
        offers = [
            f"I can show the Merck architecture and where it would sit on top of {company}'s stack.",
            f"I can walk through the strategy-layer setup Merck uses and map it to {company}.",
            f"I can share the stack view Merck uses and where the same layer would fit at {company}.",
        ]
    else:
        offers = [
            f"I can share the spend-under-strategy benchmark we use for {industry}.",
            f"I can send the benchmark we use for {industry} and the first coverage gaps teams usually find.",
            f"I can share the benchmark view for {industry} and where teams usually start.",
        ]
    return offers[variant]


def email_parts(row: dict, angle: int) -> tuple[str, str, str]:
    variant = (int(row["id"]) + angle) % 3
    if angle == 1:
        p1 = angle1_observation(row)
        p2 = ANGLE1_PROOFS[variant]
    elif angle == 2:
        p1 = angle2_observation(row)
        p2 = ANGLE2_PROOFS[variant]
    else:
        p1 = angle3_observation(row)
        p2 = ANGLE3_PROOFS[variant]
    p3 = offer_text(row, angle, variant)
    return p1, p2, p3


def build_email(row: dict, angle: int) -> str:
    p1, p2, p3 = email_parts(row, angle)
    email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
    words = email.replace("\n", " ").split()

    if len(words) < 80:
        filler = {
            1: "That usually leaves teams reacting late to market moves.",
            2: "That planning gap usually slows decisions before execution begins.",
            3: "That usually means part of the portfolio is still running on inertia.",
        }[angle]
        p1 = f"{p1} {filler}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        words = email.replace("\n", " ").split()

    if len(words) < 80:
        angle_fillers = {
            1: "That is usually where the manual process falls behind first.",
            2: "That planning gap usually sits above the suite, not inside it.",
            3: "That is usually where teams discover how much spend is still uncovered.",
        }
        p3 = f"{p3} {angle_fillers[angle]}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        words = email.replace("\n", " ").split()

    if len(words) < 80:
        extra_proof = {
            1: "It gave category teams a faster way to keep strategy current.",
            2: "It gave category teams a dedicated place to do the planning work first.",
            3: "It gave the team a scalable way to widen strategic coverage.",
        }[angle]
        p2 = f"{p2} {extra_proof}"
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        words = email.replace("\n", " ").split()

    if len(words) < 80:
        p1 = f"{p1} The backlog is usually visible well before the board sees it."
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"
        words = email.replace("\n", " ").split()

    if len(words) > 100:
        p1 = trim_words(p1, max(18, len(p1.split()) - (len(words) - 100)))
        email = "\n\n".join([p1, p2, p3]) + "\n\nManuel Suhrcke"

    return email


def build_dm(row: dict, angle: int) -> str:
    variant = (int(row["id"]) + angle) % 3
    if angle == 1:
        observation = trim_words(angle1_observation(row), 14)
        proof = trim_words(ANGLE1_PROOFS[variant], 10)
    elif angle == 2:
        observation = trim_words(angle2_observation(row), 14)
        proof = trim_words(ANGLE2_PROOFS[variant], 10)
    else:
        observation = trim_words(angle3_observation(row), 14)
        proof = trim_words(ANGLE3_PROOFS[variant], 10)

    offer = trim_words(
        DM_OFFERS[angle][variant].format(company=row["company"], industry=row["industry"]),
        9,
    )
    dm = f"{observation} {proof} {offer}\n\nManuel"
    if len(dm.replace("\n", " ").split()) > 60:
        dm = f"{trim_words(observation, 12)} {trim_words(proof, 9)} {trim_words(offer, 8)}\n\nManuel"
    return dm


def main() -> None:
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys())

    for row in rows:
        for key, value in list(row.items()):
            row[key] = clean_text(value)
        for angle in range(1, 4):
            row[f"angle{angle}_dm"] = build_dm(row, angle)
            row[f"angle{angle}_email_body"] = build_email(row, angle)

    with CSV_PATH.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Rewrote {len(rows)} rows in {CSV_PATH}")


if __name__ == "__main__":
    main()
