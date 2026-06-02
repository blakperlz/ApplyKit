# ApplyKit — Product Requirements Document

**Author:** Jeff Watson + Claude  
**Date:** 2026-06-01  
**Status:** DRAFT — awaiting Jeff's sign-off before build  
**Version:** 3.0 (renamed ApplyKit, scheduled-first, feedback loop, volume controls)

---

## 1. Problem Statement

Job searching is a pipeline problem disguised as a writing problem. Five gaps make the process unsustainable:

1. **Discovery is manual.** The user checks career pages one at a time, reads each JD, and makes a gut call about fit. This doesn't scale past a handful of companies.

2. **No structured evaluation.** Without a consistent scoring framework, decisions drift. The 10th JD of the week gets less attention than the 1st. Anxiety drives applications to roles that were never a real fit.

3. **No ranking across opportunities.** When evaluating multiple JDs, there's no side-by-side comparison. Decisions are made one at a time without seeing the full landscape.

4. **Customization is high-effort.** The resume-customizer skill produces excellent tailored resumes and cover letters, but it takes 10-15 minutes per run. That's unsustainable for more than a few roles per week.

5. **No learning.** When the user disagrees with a decision or gets rejected, nothing feeds back into future evaluations. The process doesn't get smarter over time.

## 2. What ApplyKit Is

ApplyKit is a **scheduled job search pipeline** that works overnight and delivers ready-to-apply materials by morning. It runs five named steps:

```
Scout → Score → Rank → Craft → Apply
```

**Scout** monitors career pages and ingests new JDs. **Score** evaluates each JD across 10 weighted dimensions. **Rank** sorts by fit and assigns letter grades. **Craft** generates tailored resumes and cover letters for qualifying roles. **Apply** presents the morning's results for the user to review, approve, and submit.

The primary mode is scheduled (overnight automation). Ad-hoc mode (evaluate a single JD on demand) uses the same engine. A CLI provides power-user access to each step independently.

## 3. Success Criteria

| Criteria | Measurement |
|----------|-------------|
| Morning delivery | User wakes up to ranked results with materials ready |
| Triage speed | Score a JD in < 30 seconds |
| Batch capability | Process up to 25 JDs per overnight run |
| End-to-end delivery | Qualifying roles produce resume + cover letter automatically |
| Decision quality | Scoring agrees with user's judgment 80%+ of the time, improving over time via feedback |
| Volume control | Caps prevent more than 5 materials per run; user never drowns in output |
| Pipeline visibility | Single command shows all active applications with status and next action |
| Durability | All code in GitHub, tested, runnable from any machine with Python 3.10+ |
| Modularity | New JD sources, dimensions, or output actions can be added without rewriting core |

## 4. The Five Steps

### Step 1: Scout
Monitor target companies' career pages on a schedule. Detect new postings by diffing against a local cache of previously seen listings. New postings enter the pipeline automatically.

**Ad-hoc mode:** Accept JDs via URL, file (.pdf, .docx, .txt), or pasted text at any time.

**How detection works:** Scout fetches each career page and uses LLM-assisted extraction to identify job listing titles and URLs. This is more resilient to page format changes than CSS selectors. A SQLite cache stores previously seen postings (URL + title hash). Only new entries proceed to Score.

**Configuration:**
- `config/companies.yml` — company names, career page URLs, priority tier (dream/target/opportunistic), check frequency
- Score cap: max JDs to evaluate per run (default 25). Dream-tier companies are evaluated first.

### Step 2: Score
Evaluate each JD against the user's profile across 10 weighted dimensions.

| # | Dimension | Default Weight | What it measures |
|---|-----------|---------------|------------------|
| 1 | Role Fit | 20% | Title, scope, seniority, responsibility alignment |
| 2 | Technical Match | 15% | Stack overlap, required vs nice-to-have skills |
| 3 | Leadership Match | 15% | Team size, org scope, management expectations |
| 4 | Mission Alignment | 10% | Company mission vs user's values |
| 5 | Growth Potential | 10% | Career trajectory, learning, promotion signals |
| 6 | Compensation Signal | 10% | Salary range or inferred level vs user's target |
| 7 | Location/Remote | 5% | Remote/hybrid/onsite fit |
| 8 | Security Domain | 5% | Cybersecurity, AI safety, trust and safety relevance |
| 9 | Government Adjacency | 5% | Public sector, clearance, defense connection |
| 10 | Culture Signal | 5% | Tone, values, work-life signals, red flags |

**Output per JD:** overall score (0-100), letter grade (A/B/C/D/F), per-dimension scores with written explanations, recommendation.

**Grade scale:**
- A (90-100): "Apply immediately"
- B+ (85-89): "Apply immediately"
- B (80-84): "Strong candidate"
- C (70-79): "Consider if aligned with goals"
- D (60-69): "Skip"
- F (<60): "Skip"

**Dimensions are fully configurable.** Users can change weights, rename dimensions, add new ones, or remove ones that don't apply. A product designer might drop "Security Domain" and "Government Adjacency" in favor of "Design Craft" and "Portfolio Fit."

### Step 3: Rank
Sort all scored JDs by weighted total. Present as a ranked list with grades and recommendations. The list accumulates over time — serial evaluations build up a leaderboard alongside batch results.

**Filtering:** by grade, status, dimension, company, or date range.

### Step 4: Craft
For every role scoring above the craft threshold (default B+/85), automatically generate:
- A tailored .docx resume via the resume-customizer pipeline (unpack → edit XML → repack → render PDF)
- A matching .docx cover letter in the user's voice
- Both saved to workspace, named by company and role

**Craft cap:** max materials per run (default 5). If 12 roles score A, only the top 5 get materials. The rest are scored and ranked for manual review. The user can manually trigger Craft for any scored role later.

**Per-company thresholds:** Dream-tier companies can have lower craft thresholds than opportunistic ones.

### Step 5: Apply
The user reviews the morning's results:
- Ranked list with grades and dimension breakdowns
- Pre-built materials for qualifying roles
- Three actions per role: **Agree** (proceed to apply), **Skip** (not now), **Disagree** (flag with reason)

For roles the user agrees with, materials are ready to attach and submit. The tracker logs each application's status.

## 5. Volume Controls

Three configurable caps prevent runaway output:

| Cap | Default | What it limits |
|-----|---------|----------------|
| Score cap | 25/run | Max JDs evaluated per overnight run. Dream companies prioritized. |
| Craft threshold | B+ (85) | Minimum grade for automatic material generation. Configurable per company. |
| Craft cap | 5/run | Max materials generated per run. Top scores win the slots. |

All configurable in `config/pipeline.yml`.

## 6. Feedback Loop

When the user reviews scored roles, disagreements are captured and fed back into future scoring.

### How it works
1. **Logging:** Each disagreement is stored in SQLite: application ID, dimension scores, user verdict (agree/disagree/skip), user reason (free text), timestamp.
2. **Pattern detection:** The calibration module groups disagreements by dimension and identifies recurring patterns — e.g., "user rejected 4 roles where Compensation Signal scored below 60."
3. **Weight suggestions:** When a pattern reaches minimum sample size (default 5), ApplyKit suggests a weight adjustment: "Increase Compensation weight from 10% to 15%?" User approves or declines.
4. **Prompt calibration:** The N most recent disagreement examples are included in the evaluation prompt as few-shot context, so the scorer sees concrete cases of past mistakes.

### Guardrails
- Weight adjustments are **suggested, never automatic.** The user approves every change.
- Minimum sample size (default 5 disagreements on same pattern) before suggesting adjustments.
- Calibration history is tracked so adjustments can be rolled back.

### Outcome tracking
The tracker logs status transitions: APPLYING → INTERVIEWING → OFFERED → ACCEPTED/REJECTED. Over time, this data correlates dimension scores with real outcomes — which dimensions actually predict interviews? This is the dataset for Future F2 (outcome analytics). Data collection starts from day one.

## 7. Architecture

```
applykit/
├── applykit/
│   ├── __init__.py
│   ├── cli.py              # Click CLI: scout, score, rank, craft, status, calibrate
│   ├── scout.py            # Career page monitoring + new posting detection
│   ├── evaluator.py        # 10-dimension scoring engine
│   ├── ranking.py          # Sort, filter, compare evaluations
│   ├── crafter.py          # Orchestrate resume + cover letter generation
│   ├── pipeline.py         # End-to-end orchestrator: scout → score → rank → craft
│   ├── tracker.py          # SQLite application tracker + status state machine
│   ├── feedback.py         # Disagreement logging + calibration engine
│   ├── report.py           # Markdown report generator
│   ├── models.py           # Dataclasses, enums, state machine
│   ├── config.py           # YAML config loader
│   └── jd_parser.py        # Extract JD text from URL/PDF/DOCX/text
├── config/
│   ├── profile.yml.example # Template (real profile in .gitignore)
│   ├── scoring_weights.yml # Scoring dimensions and weights
│   ├── companies.yml.example # Company watchlist template
│   ├── pipeline.yml        # Volume caps, thresholds, schedule settings
│   ├── profile.yml         # GITIGNORED — user's real profile
│   └── companies.yml       # GITIGNORED — user's real watchlist
├── context/
│   ├── accomplishments.md.example
│   ├── summary_variants.md.example
│   ├── accomplishments.md  # GITIGNORED
│   └── summary_variants.md # GITIGNORED
├── tests/
│   ├── test_scout.py
│   ├── test_evaluator.py
│   ├── test_ranking.py
│   ├── test_crafter.py
│   ├── test_pipeline.py
│   ├── test_tracker.py
│   ├── test_feedback.py
│   ├── test_models.py
│   └── test_jd_parser.py
├── docs/
│   ├── PRD.md              # This file
│   └── PRFAQ.md            # Press release / FAQ
├── .github/
│   └── workflows/
│       └── ci.yml          # Lint + test
├── .gitignore
├── pyproject.toml
├── README.md
└── COWORK_SKILL.md         # Cowork scheduled task + ad-hoc skill
```

**Modules vs v1:**

| Module | Purpose | New in v3? |
|--------|---------|-----------|
| `scout.py` | Career page monitoring, new posting detection, cache management | Yes |
| `evaluator.py` | 10-dimension scoring engine, prompt builder, response parser | No (redesigned) |
| `ranking.py` | Sort, filter, compare, batch ranking | No (redesigned) |
| `crafter.py` | Orchestrate resume + cover letter generation via resume-customizer | Yes (was `pipeline.py` in v2) |
| `pipeline.py` | End-to-end orchestrator: scout → score → rank → craft | Yes |
| `tracker.py` | SQLite application tracker, status state machine, audit trail | No (redesigned) |
| `feedback.py` | Disagreement logging, pattern detection, weight suggestions | Yes |
| `jd_parser.py` | Extract JD text from URL/PDF/DOCX/text | No |
| `report.py` | Markdown report generator | No |
| `models.py` | Dataclasses, enums, state transitions | No (expanded) |
| `config.py` | YAML config loader with defaults | No |
| `cli.py` | Click CLI for all steps | No (expanded) |

**Extension points:**
- New JD sources: add to `scout.py` or write a new ingestion module
- New evaluation dimensions: edit `config/scoring_weights.yml`
- New output actions: add a handler to `crafter.py`
- New feedback signals: extend `feedback.py`

## 8. Integration with Resume-Customizer

ApplyKit's `crafter.py` calls the resume-customizer skill. The handoff:
1. ApplyKit provides: parsed JD text, company name, role title
2. Resume-customizer does: unpack base resume → edit XML → repack → render PDF → generate cover letter → render PDF
3. ApplyKit receives: file paths to the finished .docx and .pdf files
4. ApplyKit updates the tracker status to APPLYING

The resume-customizer remains the document generation engine. ApplyKit is the decision and orchestration layer.

## 9. CLI Commands

| Command | What it does |
|---------|-------------|
| `applykit scout` | Check monitored career pages, report new postings |
| `applykit score <source>` | Evaluate a single JD (URL, file, or text) |
| `applykit rank` | Show ranked leaderboard of all scored roles |
| `applykit craft <id>` | Generate resume + cover letter for a specific role |
| `applykit status` | Pipeline summary across all applications |
| `applykit status <id>` | Detail view for one application |
| `applykit track add <company> <role>` | Manually log an application |
| `applykit track update <id> <status>` | Update application status |
| `applykit feedback <id> <agree\|disagree\|skip>` | Log feedback on a scored role |
| `applykit calibrate` | Review disagreement patterns, suggest weight adjustments |
| `applykit run` | Execute full pipeline: scout → score → rank → craft |

## 10. Cowork Integration

**Scheduled mode:** A Cowork scheduled task runs `applykit run` on a cron (e.g., daily at 5 AM). The task is self-contained — it has its own SKILL.md with the full pipeline prompt. Results are available when the user opens Cowork in the morning.

**Ad-hoc mode:** The user pastes a JD or URL in Cowork and says "evaluate this." The COWORK_SKILL.md routes to `applykit score` + `applykit craft` as appropriate.

**Morning review:** The user says "show me this morning's results" and gets the ranked list with grades, breakdowns, and links to generated materials.

## 11. Design Principles

- **Scheduled-first.** The primary experience is waking up to results, not driving a tool. Ad-hoc mode is the secondary path.
- **Modular.** Scout, Score, Rank, Craft, and Apply are independent components. Each can evolve, be replaced, or be extended without touching the others.
- **Self-improving.** Feedback and outcome tracking make scoring better over time. The system learns from the user's real preferences and real results.
- **Volume-controlled.** Three caps prevent the pipeline from generating more than the user can meaningfully review.
- **Local-first.** All data stays on the user's machine. SQLite, YAML, local files.
- **No personal data in git.** Profile, accomplishments, company watchlist, and context files are gitignored. Templates checked in.
- **CLI for power users.** Every step is accessible from the command line for scripting and debugging.

## 12. Build Plan

| Step | What | Depends on |
|------|------|------------|
| 1 | Write core modules: models, config, jd_parser | PRD sign-off |
| 2 | Write evaluator, ranking | Step 1 |
| 3 | Write scout, crafter, pipeline | Steps 1-2 |
| 4 | Write tracker, feedback, report | Step 1 |
| 5 | Write CLI | Steps 1-4 |
| 6 | Write tests | Steps 1-5 |
| 7 | Run tests in sandbox | Step 6 |
| 8 | Write config templates and .gitignore | Step 1 |
| 9 | Initialize git, create GitHub repo, push | Step 7 passing |
| 10 | Add as submodule to Recruiter-resume | Step 9 |
| 11 | Test end-to-end: evaluate a real JD → craft materials | Step 9 |
| 12 | Set up Cowork scheduled task | Step 11 |
| 13 | Save project memory | Step 12 |

## 13. Constraints

- Python 3.10+
- Dependencies: Click, PyYAML, pdfplumber, python-docx, requests (all lightweight)
- anthropic SDK is optional (`pip install applykit[standalone]`) for API mode
- SQLite only — no server dependencies
- Must work as scheduled task, ad-hoc in Cowork, and standalone CLI
- Personal data never committed to GitHub

## 14. Future Features (Design For, Don't Build)

| # | Feature | Architecture hook |
|---|---------|------------------|
| F1 | **Interview prep** | Trigger on status = INTERVIEWING → generate prep from JD + profile. New output action in crafter. |
| F2 | **Outcome analytics** | Correlate dimension scores with interview/offer outcomes → suggest reweights. Reads feedback + tracker data. |
| F3 | **Multi-profile support** | Config swap for different career directions. Config layer change only. |
| F4 | **Job board integrations** | New Scout sources (Indeed, LinkedIn) — same Score/Rank/Craft pipeline. |

## 15. Out of Scope (for MVP)

- Job board API integrations
- Interview prep generation
- Outcome analytics dashboard
- Web UI
- Multi-user support
