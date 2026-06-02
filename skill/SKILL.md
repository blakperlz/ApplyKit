---
name: applykit
description: Use when the user wants to evaluate a job description, score a role against their profile, or generate a tailored resume and cover letter on demand. Triggers include pasting a JD or job URL and saying "evaluate this", "score this role", "is this a good fit?", or "craft materials for this". This is ApplyKit's ad-hoc Cowork mode — the on-demand counterpart to the overnight scheduled pipeline.
---

# ApplyKit — Ad-hoc mode

Score a single job description and, if it qualifies, craft application materials.
This is the on-demand path. The overnight automation lives in
`SCHEDULED_SKILL.md`. Both write to the same SQLite database, so results from
either mode show up in the same pipeline view.

## Data contract (shared with the CLI)

- **Database:** `applykit.db` (SQLite). Schema is defined in `applykit/db.py` —
  seven tables: `postings_cache`, `applications`, `evaluations`,
  `status_history`, `feedback`, `calibration_log`, `crafted_materials`.
- **Config:** `config/config.yml` — sections `profile`, `scoring`, `companies`,
  `pipeline`. Load it to get the user's dimensions, weights, and caps.
- **Profile narrative:** `context/profile.md` — long-form accomplishments,
  summary variants, and voice for the crafter.

Never invent scores or facts. Score only from the JD and the user's real profile.

## Workflow

### 1. Ingest the JD
Accept a URL, a file (`.pdf`/`.docx`/`.txt`), or pasted text.
- URL → fetch the page and extract the clean JD text (title, company,
  responsibilities, requirements). Strip nav/boilerplate.
- File → read it. Paste → use as-is.

### 2. Load config + profile
Read `config/config.yml` for the scoring dimensions and weights, and
`context/profile.md` for the narrative. If `config/config.yml` is missing, tell
the user to copy `config/config.yml.example` and fill it in.

### 3. Pull calibration examples
Query the last N disagreements (N = `pipeline.calibration_examples`, default 5):
```sql
SELECT a.company, a.role, f.reason
FROM feedback f JOIN applications a ON a.id = f.app_id
WHERE f.verdict = 'disagree' ORDER BY f.id DESC LIMIT 5;
```
Include them in your scoring reasoning as cases to learn from.

### 4. Score across every configured dimension
For each dimension, assign 0–100 with a one-sentence rationale. Compute the
weighted overall:  `sum(score * weight) / sum(weight)`. Map to a grade:

| Grade | Range | Recommendation |
| --- | --- | --- |
| A  | 90–100 | Apply immediately |
| B+ | 85–89  | Apply immediately |
| B  | 80–84  | Strong candidate |
| C  | 70–79  | Consider if aligned with goals |
| D  | 60–69  | Skip |
| F  | <60    | Skip |

### 5. Persist
- Insert an `applications` row (status `new`), then `scored`.
- Insert an `evaluations` row with `dimension_scores` as a JSON array of
  `{key,label,score,weight,explanation}`, plus `overall_score`, `grade`,
  `recommendation`, `source`, `raw_jd`, `evaluated_at` (UTC ISO-8601).
- Record the status change in `status_history`.

### 6. Present the breakdown
Show the overall grade, the per-dimension table, and the recommendation. Be
honest about weak dimensions — an A overall with an F on Compensation tells the
user something specific.

### 7. Craft (if it qualifies)
If the grade meets the craft threshold (`pipeline.craft_threshold`, or the
company's override in `companies`), offer to generate materials. On yes, invoke
the **resume-customizer** skill to produce a tailored `.docx` resume and a
matching `.docx` cover letter in the user's voice. Save them named
`<Company>_<Role>_resume.docx` / `_cover_letter.docx`, record paths in
`crafted_materials`, and move status to `crafted`.

### 8. Feedback
Invite the user to agree / skip / disagree. On disagree, capture the reason and
a snapshot of the dimension scores into `feedback`. This is what makes scoring
improve over time (step 3).

## Volume discipline
Even ad-hoc, respect the spirit of the caps: don't auto-craft for sub-threshold
roles, and don't generate materials the user didn't ask for.
