# Session Handoff — ApplyKit

Read this first. It captures the current state of ApplyKit and what's left.

## Status: BUILT, TESTED, PUSHED. One activation step remains.

ApplyKit is a scheduled job-search pipeline (Scout → Score → Rank → Craft → Apply).
The full MVP was built per `docs/PRD.md` (v3.0) and `docs/ADR-001-architecture.md`.

- **Code:** 12 modules + Click CLI, built bottom-up per the ADR dependency graph.
- **Tests:** 64 passing (`pytest -q`). CI on Python 3.10–3.12.
- **Verified live:** scored two real job postings end-to-end (see below).

## What's done

| Area | State |
|------|-------|
| Modules | models, config, db, jd_parser, evaluator, ranking, tracker, feedback, report, scout, crafter, pipeline, cli — all written, compile, import |
| Data contract | One SQLite DB, 7 tables (`applykit/db.py`) |
| Scoring | configurable weighted dimensions; weighted overall + A–F grade |
| Volume caps | score_cap, craft_threshold, craft_cap (per-company override works) |
| Feedback | disagreement logging + prompt calibration (MVP scope) |
| Cowork skills | `skill/SKILL.md` (ad-hoc), `skill/SCHEDULED_SKILL.md` (overnight) |
| Overnight task | `COWORK_SCHEDULED_TASK.md` — ready-to-paste Cowork scheduled-task prompt (midnight daily) |
| Multi-profile | Proven via `profiles/<name>/` + CLI `--config/--db/--profile` flags |

## Live test results

Two real postings scored end-to-end, demonstrating the engine generalizes across
very different users via config alone:

- **Profile A** (AI/security leadership) — a frontend engineering-manager role →
  **81.2 (B)**, persisted, ranked, qualified for craft.
- **Profile B** (education / nonprofit, a different dimension set) — a program
  manager role → **82.4 (B)**. Same engine, dimensions swapped via config
  (security/government dropped; education/mission/cultural dimensions added).

Per-person configs, profile narratives, and databases live under `profiles/`,
which is gitignored — no personal data is committed.

## THE ONE REMAINING STEP (pipeline → live)

Claude Code cannot create a Cowork-native scheduled task. To go live:
1. Open a regular Cowork session.
2. Paste the contents of `COWORK_SCHEDULED_TASK.md` (below its first divider).
3. (Recommended) Dry-run the prompt once by hand first; confirm a good
   `ApplyKit_Morning_Brief.html`; then schedule it (midnight daily).

## TODO — come back to this

- [ ] **Onboard a second profile fully.** Score → Rank works for any profile
      today. Craft requires a per-person document-generation setup (a base resume
      + a resume-customizer config). To finish a new person: add their base
      resume + customizer setup, then give them an overnight task like the first.
- [ ] Optional: feedback pattern-detection / automated weight suggestions
      (ADR-001 Tension 5 fast-follow; needs ~15–20 evaluations of data first).

## Local-only files (gitignored — never committed)

`config/config.yml`, `context/profile.md`, `profiles/`, `*.db`. Templates
(`config/config.yml.example`, `context/profile.md.example`) are committed.
