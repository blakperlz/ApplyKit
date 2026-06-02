"""CLI-mode orchestrator: scout -> score -> rank -> craft.

Per ADR-001 Tension 1 this is the *CLI* pipeline. The Cowork scheduled task has
its own orchestration in ``skill/SCHEDULED_SKILL.md``. Both write identical
records to the same SQLite database.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .config import Config
from .crafter import craft_cli
from .evaluator import evaluate
from .feedback import calibration_examples
from .jd_parser import parse
from .models import Application, ApplicationStatus, CraftedMaterial, Evaluation
from .ranking import rank, select_for_craft
from .scout import Extractor, scout_all
from .tracker import add_application, save_evaluation, update_status


@dataclass
class RunResult:
    """Outcome of a full pipeline run, for reporting."""

    new_postings: int = 0
    evaluations: list[Evaluation] = field(default_factory=list)
    crafted: list[CraftedMaterial] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def score_source(
    conn: sqlite3.Connection,
    source: str,
    config: Config,
    *,
    profile_narrative: str = "",
    api_key: Optional[str] = None,
) -> tuple[Application, Evaluation]:
    """Score one JD source end-to-end: parse -> evaluate -> persist app + evaluation.

    Creates an application, scores the JD (with calibration examples drawn from
    past disagreements), saves the evaluation, and advances status to SCORED.
    """
    parsed = parse(source)
    examples = calibration_examples(conn, config.pipeline.get("calibration_examples", 5))
    evaluation = evaluate(
        parsed.text,
        config,
        profile_narrative=profile_narrative,
        calibration_examples=examples,
        source=parsed.source,
        api_key=api_key,
    )
    app = add_application(conn, evaluation.company, evaluation.role, url=parsed.source)
    evaluation.app_id = app.id
    save_evaluation(conn, evaluation, app_id=app.id)
    update_status(conn, app.id, ApplicationStatus.SCORED, note="scored by pipeline")
    return app, evaluation


def run(
    conn: sqlite3.Connection,
    config: Config,
    *,
    extractor: Optional[Extractor] = None,
    fetcher: Optional[Callable[[str], str]] = None,
    profile_narrative: str = "",
    out_dir: str | Path = "materials",
    api_key: Optional[str] = None,
) -> RunResult:
    """Execute scout -> score -> rank -> craft, honouring the volume caps.

    ``extractor`` is required to run Scout; if omitted, scouting is skipped and
    only previously cached/ad-hoc work proceeds (useful in tests).
    """
    result = RunResult()
    pipe = config.pipeline
    score_cap = int(pipe.get("score_cap", 25))
    craft_cap = int(pipe.get("craft_cap", 5))
    craft_threshold = pipe.get("craft_threshold", "B+")

    # --- Scout ---
    postings = []
    if extractor is not None:
        postings = scout_all(conn, config, extractor=extractor, fetcher=fetcher)
    result.new_postings = len(postings)

    # --- Score (capped; scout_all already ordered dream-first) ---
    to_score = postings[:score_cap]
    apps_by_eval: dict[int, Application] = {}
    for posting in to_score:
        try:
            app, evaluation = score_source(
                conn, posting.url, config,
                profile_narrative=profile_narrative, api_key=api_key,
            )
            result.evaluations.append(evaluation)
            if evaluation.app_id is not None:
                apps_by_eval[evaluation.app_id] = app
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"score {posting.url}: {exc}")

    # --- Rank + select for craft (threshold + cap) ---
    chosen = select_for_craft(
        result.evaluations,
        threshold=craft_threshold,
        cap=craft_cap,
        company_threshold=config.company_craft_threshold,
    )

    # --- Craft ---
    for evaluation in chosen:
        if evaluation.app_id is None:
            continue
        try:
            material = craft_cli(
                evaluation, config,
                app_id=evaluation.app_id, out_dir=out_dir,
                profile_narrative=profile_narrative, conn=conn, api_key=api_key,
            )
            update_status(conn, evaluation.app_id, ApplicationStatus.CRAFTED,
                          note="materials generated")
            result.crafted.append(material)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"craft {evaluation.company}: {exc}")

    result.evaluations = rank(result.evaluations)
    return result
