---
name: applykit-overnight
description: ApplyKit's overnight scheduled pipeline. Run as a Cowork scheduled task (e.g. daily at 5 AM) to monitor career pages, score new postings, rank them, craft materials for the top qualifying roles, and leave a morning brief. This is the primary, scheduled-first experience — the user wakes up to a curated, ranked inbox with materials ready.
---

# ApplyKit — Overnight pipeline

Run end-to-end without the user present: **Scout → Score → Rank → Craft**, then
write a morning brief. Honour the volume caps so the user never drowns. Use the
same `applykit.db` and `config/config.yml` as ad-hoc mode.

## Inputs
- `config/config.yml` — `companies` watchlist, `scoring` dimensions/weights,
  `pipeline` caps (`score_cap`, `craft_threshold`, `craft_cap`).
- `context/profile.md` — narrative for scoring + crafting.
- `applykit.db` — `postings_cache` for the new-vs-seen diff.

## Steps

### 1. Scout (dream tier first)
For each company in `companies`, ordered dream → target → opportunistic:
1. Fetch the careers page.
2. Extract `(title, url)` for each listing (you are the LLM extractor — this is
   robust to layout changes; ADR-001 Tension 2).
3. Diff against `postings_cache`: for each listing compute a stable url hash and
   keep only rows where `(company, url_hash)` is absent.
4. Insert new postings into `postings_cache` (`company, title, url, url_hash,
   first_seen`).
If a single company's page fails, log it and continue — never abort the run.

### 2. Score (respect `score_cap`)
Take up to `score_cap` new postings (dream tier already first). For each: fetch
the JD text, pull the last 5 disagreements for calibration, score every
configured dimension 0–100 with rationale, compute the weighted overall and
grade (scale in `SKILL.md`). Persist an `applications` row (`new` → `scored`)
and an `evaluations` row (JSON `dimension_scores`).

### 3. Rank
Sort all of tonight's evaluations best-first by overall score.

### 4. Craft (respect `craft_threshold` and `craft_cap`)
From the ranked list, select roles whose grade meets the threshold (per-company
override wins). Take at most `craft_cap` — the top scorers win the slots. If 12
qualify and the cap is 5, craft the top 5 and leave the rest scored for manual
review. For each selected role, invoke **resume-customizer** to produce a
tailored `.docx` resume + cover letter, save them, record paths in
`crafted_materials`, and move status to `crafted`.

### 5. Morning brief
Write a concise summary the user sees on waking:
- Count of new postings found and roles scored.
- The ranked leaderboard with grade + recommendation per role.
- Which roles have materials ready (✅) and where the files are.
- Anything skipped due to caps, and any companies that failed to scout.

Each role offers three actions for the morning review: **Agree** (proceed to
apply), **Skip** (not now), **Disagree** (flag with a reason → `feedback`).

## Guardrails
- Caps are hard limits. Do not exceed `score_cap` or `craft_cap`.
- No personal data leaves the machine beyond the JD text sent for scoring.
- Idempotent: re-running the same night must not re-score already-cached
  postings (that's what `postings_cache` guarantees).
