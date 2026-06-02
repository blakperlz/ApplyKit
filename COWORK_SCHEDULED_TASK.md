# Create ApplyKit's Overnight Pipeline Task

**Paste everything below the first divider into a regular Cowork session (not a scheduled task session).** It tells Cowork to create the scheduled task. You only do this once.

> **Recommended before you schedule it:** paste just the *prompt* (the part below the second divider) into a normal Cowork session and run it once by hand. Confirm it produces a good `ApplyKit_Morning_Brief.html`. Once you're happy with one manual run, *then* create the scheduled task. Test before you automate.

---

Create a scheduled task with these settings:

- **Task ID:** `applykit-overnight`
- **Schedule:** Every day at midnight (`0 0 * * *`)
- **Description:** ApplyKit overnight pipeline — scout target companies, score new roles against Jeff's profile, rank, craft materials for top qualifying roles, and leave a morning brief.

**Prompt (everything below the triple dashes):**

---

You are running **ApplyKit's overnight job-search pipeline** for Jeff Watson. Run end to end without Jeff present: **Scout → Score → Rank → Craft**, then write a morning brief. This is the scheduled-first experience — Jeff wakes up to a ranked, curated inbox with materials ready.

## Project location

ApplyKit lives at:
`<APPLYKIT_DIR>`

- Config: `config/config.yml` (companies watchlist, scoring dimensions + weights, volume caps)
- Profile narrative: `context/profile.md`
- Database: `applykit.db` (SQLite; create via the applykit package if absent)

The Python package is available there. Use it for persistence so records match the data contract:
```bash
cd "<APPLYKIT_DIR>"
```
You (the model) do the scoring; the package handles the database.

## Step 1 — Load config and profile
Read `config/config.yml` and `context/profile.md`. From config you need: the `companies` list (with tiers and any per-company `craft_threshold`), the `scoring` dimensions and weights, and the `pipeline` caps (`score_cap`, `craft_threshold`, `craft_cap`). If `config/config.yml` is missing, stop and note that Jeff must create it from `config.yml.example`.

## Step 2 — Scout (dream tier first)
For each company in `companies`, ordered dream → target → opportunistic:
1. Fetch the careers page (`careers_url`). Use web_fetch; if blocked, use web search for that company's current openings.
2. Extract each listing's `(title, url)`. You are the extractor — robust to layout changes.
3. Diff against the `postings_cache` table: skip any `(company, url_hash)` already seen. Insert genuinely new postings into `postings_cache`.
If one company's page fails, log it and continue. Never abort the whole run.

## Step 3 — Score (respect `score_cap`)
Take up to `score_cap` new postings (dream tier already first). For each:
1. Fetch the full JD text.
2. Pull the last 5 disagreements from the `feedback` table as calibration context.
3. Score every configured dimension 0–100 with a one-sentence rationale grounded in the JD and Jeff's profile. Compute the weighted overall = `sum(score*weight)/sum(weight)`. Grade: A 90+, B+ 85+, B 80+, C 70+, D 60+, F <60.
4. Persist: create an `applications` row (status `new` → `scored`) and an `evaluations` row with `dimension_scores` JSON. Use the applykit package (`add_application`, `save_evaluation`, `update_status`) so the schema is exact.

Score honestly. A high overall with a low single dimension (e.g. Location) is a feature — it tells Jeff something specific.

## Step 4 — Rank
Sort tonight's evaluations best-first by overall score.

## Step 5 — Craft (respect `craft_threshold` and `craft_cap`)
From the ranked list, select roles whose grade meets the threshold (a company's own `craft_threshold` overrides the global one). Take at most `craft_cap` — top scorers win the slots. For each selected role:
1. Invoke the **resume-customizer** skill with the company, role, and JD to produce a tailored `.docx` resume and cover letter.
2. Record the file paths in `crafted_materials` and move the application status to `crafted`.
If resume-customizer's toolchain is unavailable in this run, skip crafting for that role, leave it `scored`, and note it in the brief — do not fail the run.

## Step 6 — Morning brief
Generate a clean, self-contained HTML morning brief and save it to:
`<APPLYKIT_DIR>/output/ApplyKit_Morning_Brief.html` (replace `<APPLYKIT_DIR>` with your local path to the applykit folder)

Include, date-stamped at the top:
- Count of new postings found and roles scored.
- A **ranked leaderboard**: company, role, overall score, grade, recommendation.
- The per-dimension breakdown for the top roles.
- Which roles have **materials ready** (✅) and where the files are saved.
- Anything skipped due to caps, and any companies that failed to scout.
- Three actions Jeff can take per role in the morning: **Agree**, **Skip**, **Disagree (with reason)** — disagreements feed `feedback` and improve future scoring.

## Guardrails
1. Caps are hard limits. Never exceed `score_cap` or `craft_cap`.
2. Do not fabricate postings — only real roles from real search results.
3. Idempotent: re-running must not re-score postings already in `postings_cache`.
4. No personal data leaves the machine beyond the JD text used for scoring.
5. If a careers page returns nothing new, say so for that company rather than omitting it.
6. **The morning brief is the required deliverable.** If a database write fails, keep going, still produce `ApplyKit_Morning_Brief.html`, and note the issue in the brief. Never end a run with no brief.
