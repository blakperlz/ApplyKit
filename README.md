# ApplyKit

A scheduled job-search pipeline that works overnight and hands you ready-to-apply
materials by morning.

```
Scout → Score → Rank → Craft → Apply
```

**Scout** monitors career pages. **Score** evaluates each JD across 10 weighted,
fully configurable dimensions. **Rank** sorts by fit and grades A–F. **Craft**
generates a tailored resume + cover letter for qualifying roles. **Apply** is
your morning review: approve, skip, or disagree.

The primary experience is *scheduled-first* — wake up to a curated, ranked inbox.
There is also an ad-hoc mode (evaluate a single JD on demand) and a power-user CLI.

## Two runtimes, one data contract

ApplyKit runs in two places that share **one SQLite database and one YAML config**
(ADR-001):

| Runtime | What it is | Use |
| --- | --- | --- |
| **Cowork** (primary) | Prompt-driven skills (`skill/`) | Scheduled overnight runs + ad-hoc scoring |
| **CLI** (secondary) | This Python package | Scripting, debugging, power users |

The Cowork layer produces finished `.docx`/`.pdf` materials via the
resume-customizer skill. The CLI produces markdown drafts (it can't drive the
full XML pipeline) — see ADR-001 Tension 4.

## Install (CLI)

Requires Python 3.10+.

```bash
pip install -e .                 # core: click + pyyaml
pip install -e ".[parse]"        # + URL/PDF/DOCX JD parsing
pip install -e ".[standalone]"   # + Anthropic SDK for CLI scoring/crafting
pip install -e ".[dev]"          # + pytest
```

## Configure

```bash
cp config/config.yml.example   config/config.yml      # profile, scoring, companies, pipeline
cp context/profile.md.example  context/profile.md     # accomplishments, summaries, voice
```

Both real files are gitignored — **no personal data is ever committed.** Edit
them with your details, watchlist, and dimension weights.

## CLI usage

| Command | Does |
| --- | --- |
| `applykit score <url\|file\|text>` | Evaluate one JD |
| `applykit rank` | Leaderboard of all scored roles |
| `applykit status` | Pipeline summary across applications |
| `applykit craft <app_id>` | Generate materials for a scored role |
| `applykit track add <company> <role>` | Manually log an application |
| `applykit track update <app_id> <status>` | Move an application's status |
| `applykit feedback <app_id> <agree\|disagree\|skip> --reason ...` | Log feedback |
| `applykit calibrate` | Review disagreement patterns |
| `applykit run` | Full pipeline (scout requires Cowork-mode extraction) |

> **Scout note:** automated career-page monitoring uses LLM extraction and runs
> in Cowork, where calls are free (ADR-001 Tension 2). The CLI focuses on
> ad-hoc scoring, ranking, crafting, and tracking.

## Scoring dimensions

Ten defaults (Role Fit 20%, Technical Match 15%, Leadership Match 15%, Mission
Alignment 10%, Growth Potential 10%, Compensation Signal 10%, Location/Remote 5%,
Security Domain 5%, Government Adjacency 5%, Culture Signal 5%). Rename, reweight,
add, or remove any of them in `config/config.yml` — weights are normalised.

## Feedback loop

Disagreements are logged with the dimension scores and your reason, then injected
into future scoring prompts as calibration examples. `applykit calibrate` shows
the patterns so you can adjust weights by hand. (Automated weight suggestions are
a planned fast follow — ADR-001 Tension 5.)

## Develop

```bash
pytest -q
```

Architecture and rationale: [`docs/PRD.md`](docs/PRD.md),
[`docs/PRFAQ.md`](docs/PRFAQ.md), [`docs/ADR-001-architecture.md`](docs/ADR-001-architecture.md).

## License

MIT.
