# CV Optimization System

## Goal
Given a job description, produce a tailored CV that maximizes both ATS score and human
recruiter relevance — without fabricating experience.

---

## What the research says actually moves callbacks

| Change | Callback multiplier |
|---|---|
| Tailored vs. generic resume | ~3–4× |
| Title aligned to job title | 3.5× |
| ATS-optimized formatting | ~3× |
| Quantified bullets | +credibility signal |
| LinkedIn link included | +71% |

Bottom line: title/summary alignment and bullet reordering are the highest-ROI moves.
Most people never reorder — they just add keywords. Reordering is free and often more
impactful.

---

## 6-Layer Optimization Process (ordered by ROI)

### Layer 1 — JD Deconstruction
Parse the JD before touching the CV.

Extract:
- Exact job title (we mirror this in your CV header)
- 20–25 keywords (hard skills, tools, soft skills)
- 4–5 core competencies they're actually hiring for
- Must-haves vs. nice-to-haves
- Language patterns (how they describe work: "led" vs "managed" vs "drove")

Output: ranked keyword list + competency map

---

### Layer 2 — Title & Summary Rewrite (highest ROI)
- Mirror the exact job title from the JD in your CV header
- Rewrite your 3–4 line summary to: signal immediate relevance, use their language,
  hit 2–3% keyword density in the summary alone
- This is what a recruiter reads in the first 7 seconds — if it doesn't match, they stop

Rule: preserve the structure of the header (the "four lines") — only the words change.

---

### Layer 3 — Competency Mapping
For each of the 4–5 core competencies extracted from the JD:
- Find the 1–2 existing bullets that best demonstrate it
- If none exists, flag the gap (we don't fabricate — we note it)
- Assign relevance score (high / medium / low) to every existing bullet

This drives bullet reordering in Layer 4.

---

### Layer 4 — Bullet Reordering (free ROI)
- Within each role, move the two highest-relevance bullets to positions 1–2
- 80% of recruiter attention in an initial scan lands on bullets 1–2 per role
- No new content written — just reorder

---

### Layer 5 — Bullet Rewriting
Rewrite the top 5–6 bullets (across all roles) to:
- Use JD language where authentic ("scaled" → "drove revenue growth", etc.)
- Sharpen quantification (add metrics if missing)
- Lead with action verbs they use in the JD

Formula: `[JD Action Verb] + [Context] + [Quantified Outcome]`

Hard rules:
- Never invent metrics you don't have
- Never claim skills you haven't used
- If a bullet can't be reframed authentically, leave it and flag it
- Preserve any "locked" lines the user has specified as unchanged

---

### Layer 6 — Keyword Density Pass
Final sweep:
- Check top 10 JD keywords appear at least once
- Verify skills section covers all required tools/skills from JD
- Target 1.5–2% overall keyword density (>3% looks like stuffing)

---

## Output format

For each optimization run, produce:

1. **JD Analysis** — keyword list, competency map, gap flags
2. **Tailored CV** — full CV with changes marked (what changed and why)
3. **Change log** — what was reordered, rewritten, or added, so you can review and
   accept/reject each change
4. **Locked lines** — confirm these were preserved unchanged

---

## What stays locked
User specifies up to N lines/bullets that must not change. These are preserved verbatim.
If a locked line conflicts with JD alignment, it's flagged but not overridden.

---

## Workflow (how we run this each time)

```
1. User provides: job description + any new locked-line updates
2. Layer 1: JD deconstruction (2 min)
3. Layer 2–6: CV tailoring against base CV
4. Output: full tailored CV + change log
5. User reviews, accepts/rejects changes
6. Save to: cv/tailored/[company]-[role].md
```

---

## File structure

```
cv/
  base-cv.md            ← master CV (user maintains this)
  tailored/
    [company-role].md   ← one file per application
```

---

## Next step
User provides:
1. Their current CV (paste as text)
2. The job description
3. Which lines/bullets are locked (if any — up to 4)

Then we run the full 6-layer process.
