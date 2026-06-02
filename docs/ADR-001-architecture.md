# ADR-001: ApplyKit System Architecture

**Status:** Proposed  
**Date:** 2026-06-01  
**Deciders:** Jeff Watson  
**Author:** Claude (architecture review of PRD v3.0 and PR/FAQ)

---

## Context

The PRD describes ApplyKit as a scheduled job search pipeline with five steps (Scout → Score → Rank → Craft → Apply), a feedback loop, volume controls, and both scheduled and ad-hoc modes. The architecture section lists 12 Python modules in a Click CLI package.

After reviewing both documents, I identified **six architectural tensions** in the current design that need resolution before building. Each is a decision point with real trade-offs.

---

## Tension 1: Two Runtime Models, One Codebase

### The problem

The PRD says "scheduled-first" and "Cowork-first" — but these are fundamentally different execution environments.

**In Cowork scheduled mode:** Claude is the runtime. There's no Python process. A scheduled task fires, Claude reads the SKILL.md prompt, and executes the pipeline conversationally — calling tools (WebFetch, Read, Write, bash) as needed. The "code" is a prompt, not a Python package.

**In standalone CLI mode:** A Python process runs. Click parses commands. The anthropic SDK makes API calls. The code is a real Python package with imports and dependencies.

The PRD's architecture assumes both modes share `applykit/` Python modules. But Cowork mode doesn't import Python modules — it follows a SKILL.md prompt. The shared surface is **data formats and storage**, not code.

### Decision

**Cowork is primary. The Python package is the secondary interface.**

Design the system as two layers:

| Layer | What it is | Who uses it |
|-------|-----------|-------------|
| **Data layer** | SQLite schema, YAML configs, file naming conventions | Both |
| **Cowork layer** | SKILL.md prompts that read configs, call tools, write to SQLite | Scheduled + ad-hoc in Cowork |
| **CLI layer** | Python package that reads configs, calls Anthropic API, writes to SQLite | Power users, standalone mode |

Both layers read/write the same SQLite database and YAML configs. They share the data contract, not the execution logic. This means:

- The Cowork skill doesn't import `applykit/evaluator.py` — it has its own evaluation prompt in SKILL.md
- The CLI package doesn't depend on Cowork — it calls the Anthropic API directly
- Both produce identical SQLite records and file outputs

### Consequence

The Python package is smaller than the PRD suggests. It doesn't need to be the "source of truth" for evaluation logic — it's one of two clients that share a data contract. The SKILL.md prompt is the other client.

**What this changes in the PRD:** `pipeline.py` becomes a CLI-only orchestrator. The Cowork scheduled task has its own orchestration in SKILL.md. `crafter.py` in CLI mode calls the Anthropic API directly rather than invoking the resume-customizer skill (which is Cowork-only).

---

## Tension 2: Scout's LLM Dependency

### The problem

Scout uses "LLM-assisted extraction" to parse career pages. Every Scout run sends page HTML to Claude and asks it to extract job listings. This means:

- Each company monitored costs one LLM call per check, even if nothing changed
- In Cowork scheduled mode, this is fine (included in the session)
- In standalone CLI mode, checking 20 companies costs $0.20-0.40 in API calls per run, just for Scout — before any scoring happens

The PR/FAQ says this is "more resilient to format changes than CSS selectors." That's true, but it's also the most expensive possible approach to page diffing.

### Options

**Option A: LLM-first (current PRD)**

| Dimension | Assessment |
|-----------|-----------|
| Complexity | Low — one approach for all pages |
| Cost | High — one LLM call per company per run |
| Resilience | High — handles format changes automatically |
| Offline capability | None — requires API/Cowork for Scout |

**Option B: HTML-first with LLM fallback**

| Dimension | Assessment |
|-----------|-----------|
| Complexity | Medium — two code paths |
| Cost | Low — LLM only when HTML parsing fails |
| Resilience | High — graceful degradation |
| Offline capability | Partial — basic Scout works offline |

**Option C: RSS/structured data first, LLM last resort**

| Dimension | Assessment |
|-----------|-----------|
| Complexity | High — three code paths |
| Cost | Lowest — most companies never need LLM |
| Resilience | High — multiple fallbacks |
| Offline capability | Full for RSS-enabled companies |

### Decision

**Option A for MVP.** Scout runs inside Cowork scheduled tasks where LLM calls are free. The complexity of tiered extraction isn't worth it until standalone mode is the primary use case (it isn't). Add Option B later if CLI Scout becomes a real workflow.

### Consequence

Scout is tightly coupled to the LLM runtime. This is acceptable because Scout only runs in scheduled mode, which is always inside Cowork. If a user wants CLI-only Scout, they pay the API cost.

---

## Tension 3: Single SQLite Database Scope

### The problem

The PRD puts everything in SQLite: application tracking, posting cache (Scout), evaluation results (Score), feedback/disagreements, calibration history, and status audit trail. That's six concerns in one database file.

### Decision

**One database, multiple tables. This is correct for a single-user local tool.**

SQLite handles concurrent reads fine. There's only one writer at a time (either the scheduled task or the user via CLI). Splitting into multiple `.db` files adds complexity for zero benefit in a single-user system.

**Schema should be designed upfront** with clear table boundaries:

| Table | Owner | Purpose |
|-------|-------|---------|
| `postings_cache` | Scout | Previously seen job listings (URL hash, title, first_seen, company) |
| `applications` | Tracker | Application records (company, role, url, status, created_at) |
| `evaluations` | Score | Scoring results (app_id FK, overall_score, grade, dimension_scores JSON, raw_jd, evaluated_at) |
| `status_history` | Tracker | Audit trail (app_id FK, from_status, to_status, timestamp, note) |
| `feedback` | Feedback | User verdicts (app_id FK, verdict, reason, dimension_snapshot JSON, timestamp) |
| `calibration_log` | Feedback | Weight adjustment history (old_weights JSON, new_weights JSON, trigger_pattern, accepted, timestamp) |
| `crafted_materials` | Crafter | File paths to generated materials (app_id FK, resume_path, cover_letter_path, crafted_at) |

### Consequence

One `applykit.db` file, seven tables. Portable, backupable, grep-able. The schema is the data contract between the Cowork layer and the CLI layer.

---

## Tension 4: Crafter's Coupling to Resume-Customizer

### The problem

The Craft step calls the resume-customizer skill. But the resume-customizer is a Cowork skill that manipulates .docx XML through a complex pipeline (unpack → edit XML → repack → render PDF). It depends on Cowork tools (Read, Write, Edit, bash with soffice) and a specific base resume file.

In Cowork mode, this works — Claude has access to the skill and all the tools. In standalone CLI mode, this doesn't work. The CLI can't invoke a Cowork skill.

### Decision

**Crafter has two backends:**

| Mode | How Craft works |
|------|----------------|
| Cowork (primary) | Pipeline prompt invokes the resume-customizer skill directly. Full XML editing pipeline. |
| CLI (secondary) | Crafter calls the Anthropic API with a simplified prompt that generates resume and cover letter content as markdown. The user manually formats or uses a template. |

The CLI backend is deliberately lower-fidelity. The full XML-editing pipeline requires Cowork's tool infrastructure. Trying to replicate it in standalone Python would mean reimplementing the entire resume-customizer — that's not worth it for a secondary use case.

### Consequence

CLI users get scored JDs + markdown drafts. Cowork users get scored JDs + finished .docx/.pdf files. This is an acceptable gap — the CLI is for power users who want scoring and tracking, not necessarily document generation.

**What this changes in the PRD:** `crafter.py` should document this two-tier approach. The CLI `applykit craft` command should be honest about its output: "Generates draft content. For production-quality .docx output, use Cowork mode."

---

## Tension 5: Feedback Loop MVP Scope

### The problem

The PRD describes three feedback mechanisms:

1. **Disagreement logging** — simple CRUD, low complexity
2. **Pattern detection** — "group by dimension, identify thresholds the user consistently rejects below" — medium complexity, needs a scoring algorithm
3. **Prompt calibration** — inject few-shot examples into the evaluation prompt — low complexity once you have the data

Pattern detection (item 2) is the hardest part. Deciding what constitutes a "pattern" requires defining: which dimensions to group by, what "consistently" means (3 rejections? 5?), how to handle correlated dimensions, and how to phrase the suggestion.

For MVP, this risks being either so simple it's useless (just count rejections per dimension) or so complex it delays the build.

### Decision

**MVP: items 1 and 3 only. Ship pattern detection as a fast follow.**

For MVP:
- Log every disagree/agree/skip with reason → SQLite `feedback` table
- Include the last 5 disagreement examples in the evaluation prompt as few-shot calibration
- `applykit calibrate` is a manual command that dumps feedback stats and lets the user manually adjust weights in `scoring_weights.yml`

For fast follow:
- Automated pattern detection that analyzes the feedback table and generates specific weight adjustment suggestions
- Requires enough data to be useful (probably 15-20 evaluations with feedback)

### Consequence

The feedback loop still works from day one — disagreements improve scoring via prompt calibration. Automated weight suggestions come later when there's enough data to make them meaningful. This avoids building a pattern detection engine for a dataset that doesn't exist yet.

---

## Tension 6: Config File Sprawl

### The problem

The PRD lists four YAML configs:
- `config/profile.yml` — user profile
- `config/scoring_weights.yml` — dimensions and weights
- `config/companies.yml` — company watchlist
- `config/pipeline.yml` — volume caps, thresholds

Plus two context files:
- `context/accomplishments.md`
- `context/summary_variants.md`

That's six files to manage before the tool does anything. For a single-user tool, this is high ceremony.

### Decision

**Consolidate to three files:**

| File | Contents | Gitignored? |
|------|----------|-------------|
| `config/config.yml` | Profile, scoring weights, pipeline caps, and company watchlist — all in one file with clear YAML sections | Yes (`.example` checked in) |
| `context/profile.md` | Accomplishments, summary variants, cover letter style — one narrative file | Yes (`.example` checked in) |
| `config/config.yml.example` | Template with dummy data and comments | No |

**Reasoning:** Scoring weights and pipeline caps rarely change independently. Profile data and company watchlist are both "about the user." Splitting them into four files creates navigation overhead for no isolation benefit. One config file with sections (`profile:`, `scoring:`, `companies:`, `pipeline:`) is easier to find, edit, and back up.

The context file (`profile.md`) stays separate because it's long-form prose, not structured YAML. But `accomplishments.md` and `summary_variants.md` merge into one file — they're both "things about Jeff that inform document generation."

### Consequence

New users create two files instead of six. The `.example` template is one file to copy and fill in. Config validation in `config.py` loads one YAML file and validates all sections.

---

## Recommended Architecture

Incorporating all six decisions:

```
applykit/
├── applykit/                    # CLI package (secondary interface)
│   ├── __init__.py
│   ├── cli.py                   # Click CLI: scout, score, rank, craft, status, calibrate, run
│   ├── scout.py                 # Career page fetch + LLM extraction
│   ├── evaluator.py             # Prompt builder + response parser + optional API caller
│   ├── ranking.py               # Sort, filter, grade assignment
│   ├── crafter.py               # Two backends: Cowork (skill invoke) / CLI (markdown draft)
│   ├── pipeline.py              # CLI-mode orchestrator: scout → score → rank → craft
│   ├── tracker.py               # SQLite CRUD for applications + status machine
│   ├── feedback.py              # Disagreement logging + manual calibrate command
│   ├── report.py                # Markdown report generator
│   ├── models.py                # Dataclasses, enums, schema constants
│   ├── config.py                # Single YAML loader with section validation
│   ├── db.py                    # SQLite connection manager + schema migration
│   └── jd_parser.py             # Extract JD text from URL/PDF/DOCX/text
├── config/
│   ├── config.yml.example       # Single config template with all sections
│   └── config.yml               # GITIGNORED — user's real config
├── context/
│   ├── profile.md.example       # Template: accomplishments + summaries + style
│   └── profile.md               # GITIGNORED — user's real profile narrative
├── skill/
│   ├── SKILL.md                 # Cowork skill definition (ad-hoc mode)
│   └── SCHEDULED_SKILL.md       # Cowork scheduled task (overnight mode)
├── tests/
│   ├── test_evaluator.py
│   ├── test_ranking.py
│   ├── test_tracker.py
│   ├── test_feedback.py
│   ├── test_models.py
│   ├── test_db.py
│   └── test_jd_parser.py
├── docs/
│   ├── PRD.md
│   ├── PRFAQ.md
│   └── ADR-001-architecture.md  # This file
├── .github/
│   └── workflows/
│       └── ci.yml
├── .gitignore
├── pyproject.toml
└── README.md
```

### Key differences from PRD v3.0

| Change | Why |
|--------|-----|
| Added `db.py` | Centralized SQLite connection manager with schema migration. Single source of truth for table definitions. |
| Added `skill/` directory | Separates Cowork skill definitions from Python code. SKILL.md (ad-hoc) and SCHEDULED_SKILL.md (overnight) are first-class artifacts, not afterthoughts. |
| Removed `COWORK_SKILL.md` from root | Moved to `skill/` directory — it's not project documentation, it's runtime configuration. |
| Consolidated configs | 4 YAML files → 1. 2 context files → 1. Total: 6 → 2 files to manage. |
| No `scout.py` tests | Scout is LLM-dependent and runs in Cowork. Unit testing it in isolation requires mocking the entire LLM interaction. Test it via integration tests against real career pages instead. |
| Feedback simplified | MVP: logging + prompt calibration only. Pattern detection deferred to fast follow. |
| Crafter two-tier | Cowork mode gets full .docx pipeline. CLI mode gets markdown drafts. Documented, not hidden. |

### Data Flow

```
                  ┌─────────────────────────────────────────────┐
                  │              applykit.db (SQLite)            │
                  │                                             │
                  │  postings_cache  applications  evaluations  │
                  │  status_history  feedback  calibration_log  │
                  │  crafted_materials                          │
                  └──────────────┬───────────────┬──────────────┘
                                 │               │
                    ┌────────────┴───┐   ┌───────┴────────────┐
                    │  Cowork layer  │   │    CLI layer        │
                    │                │   │                     │
                    │  SKILL.md      │   │  applykit/ package  │
                    │  (prompts +    │   │  (Python + Click +  │
                    │   tool calls)  │   │   Anthropic SDK)    │
                    └────────────────┘   └─────────────────────┘
                           │                      │
                    ┌──────┴──────┐        ┌──────┴──────┐
                    │  Scheduled  │        │  Ad-hoc     │
                    │  task       │        │  CLI        │
                    │  (overnight)│        │  commands   │
                    └─────────────┘        └─────────────┘
```

### Module Dependency Graph

```
models.py          ← imports nothing (pure data)
config.py          ← imports nothing
db.py              ← imports models (schema constants)
jd_parser.py       ← imports nothing from applykit
evaluator.py       ← imports models, config
ranking.py         ← imports models
tracker.py         ← imports models, db
feedback.py        ← imports models, db
crafter.py         ← imports models, config, tracker
report.py          ← imports models
scout.py           ← imports models, config, db, jd_parser
pipeline.py        ← imports scout, evaluator, ranking, crafter, tracker (leaf orchestrator)
cli.py             ← imports everything (entrypoint, no one imports it)
```

No circular dependencies. `pipeline.py` and `cli.py` are leaf nodes.

---

## Action Items

1. [ ] Jeff: approve or revise this ADR
2. [ ] Rename `career-command-center/` folder to `applykit/`
3. [ ] Write `db.py` with full schema (7 tables) before other modules
4. [ ] Write `models.py` with dataclasses matching the schema
5. [ ] Write `config.py` with single-file loader
6. [ ] Build remaining modules per dependency graph (bottom-up)
7. [ ] Write `skill/SKILL.md` and `skill/SCHEDULED_SKILL.md` as first-class deliverables
8. [ ] Write tests for testable modules (skip Scout, test via integration)
9. [ ] Create GitHub repo, push, add as submodule
10. [ ] Test end-to-end with a real JD in both Cowork and CLI modes
