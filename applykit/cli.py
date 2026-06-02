"""Click CLI — the power-user entrypoint. Leaf of the dependency graph.

Commands mirror PRD section 9: scout, score, rank, craft, status, track,
feedback, calibrate, run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

try:
    import click
except ImportError:  # pragma: no cover
    raise SystemExit(
        "ApplyKit's CLI requires Click. Install the package with `pip install -e .`."
    )

from . import __version__
from . import report as report_mod
from .config import Config, load_config
from .db import connect
from .feedback import calibration_stats, log_feedback
from .models import ApplicationStatus, DimensionScore, Evaluation, Verdict
from .pipeline import run as run_pipeline
from .pipeline import score_source
from .tracker import (
    TrackerError,
    add_application,
    latest_evaluation_for,
    list_applications,
    summary,
    update_status,
)

DEFAULT_CONFIG = "config/config.yml"
DEFAULT_DB = "applykit.db"
DEFAULT_PROFILE = "context/profile.md"


def _load(ctx) -> tuple[Config, str]:
    config = load_config(ctx.obj["config_path"])
    narrative = ""
    p = Path(ctx.obj["profile_path"])
    if p.exists():
        narrative = p.read_text(encoding="utf-8", errors="replace")
    return config, narrative


def _eval_from_row(row: dict) -> Evaluation:
    import json

    dims = [DimensionScore(**d) for d in json.loads(row["dimension_scores"])]
    return Evaluation(
        company=row["company"], role=row["role"], overall_score=row["overall_score"],
        grade=row["grade"], dimension_scores=dims, recommendation=row["recommendation"],
        source=row["source"], raw_jd=row["raw_jd"], evaluated_at=row["evaluated_at"],
        app_id=row["app_id"],
    )


@click.group()
@click.version_option(__version__, prog_name="applykit")
@click.option("--config", "config_path", default=DEFAULT_CONFIG, show_default=True,
              help="Path to config.yml")
@click.option("--db", "db_path", default=DEFAULT_DB, show_default=True,
              help="Path to the SQLite database")
@click.option("--profile", "profile_path", default=DEFAULT_PROFILE, show_default=True,
              help="Path to the profile narrative markdown")
@click.pass_context
def cli(ctx, config_path, db_path, profile_path):
    """ApplyKit — a job-search pipeline. Scout -> Score -> Rank -> Craft -> Apply."""
    ctx.ensure_object(dict)
    ctx.obj.update(config_path=config_path, db_path=db_path, profile_path=profile_path)


@cli.command()
@click.argument("source")
@click.pass_context
def score(ctx, source):
    """Evaluate a single JD (URL, file, or pasted text)."""
    config, narrative = _load(ctx)
    conn = connect(ctx.obj["db_path"])
    try:
        _app, evaluation = score_source(conn, source, config, profile_narrative=narrative)
        click.echo(report_mod.evaluation_detail(evaluation))
    finally:
        conn.close()


@cli.command()
@click.pass_context
def rank(ctx):
    """Show the ranked leaderboard of all scored roles."""
    conn = connect(ctx.obj["db_path"])
    try:
        rows = conn.execute(
            "SELECT e.* FROM evaluations e "
            "JOIN (SELECT app_id, MAX(id) AS mid FROM evaluations GROUP BY app_id) m "
            "ON e.id = m.mid"
        ).fetchall()
        evals = [_eval_from_row(dict(r)) for r in rows]
        click.echo(report_mod.ranked_table(evals))
    finally:
        conn.close()


@cli.command()
@click.pass_context
def status(ctx):
    """Pipeline summary across all applications."""
    conn = connect(ctx.obj["db_path"])
    try:
        click.echo(report_mod.status_summary(summary(conn)))
        click.echo("")
        for app in list_applications(conn):
            click.echo(f"  #{app.id} [{app.status.value}] {app.company} — {app.role}")
    finally:
        conn.close()


@cli.command()
@click.argument("app_id", type=int)
@click.option("--out", "out_dir", default="materials", show_default=True)
@click.pass_context
def craft(ctx, app_id, out_dir):
    """Generate resume + cover letter for a specific scored role."""
    from .crafter import craft_cli

    config, narrative = _load(ctx)
    conn = connect(ctx.obj["db_path"])
    try:
        row = latest_evaluation_for(conn, app_id)
        if not row:
            raise click.ClickException(f"No evaluation found for app #{app_id}.")
        evaluation = _eval_from_row(row)
        material = craft_cli(evaluation, config, app_id=app_id, out_dir=out_dir,
                             profile_narrative=narrative, conn=conn)
        update_status(conn, app_id, ApplicationStatus.CRAFTED, note="crafted via CLI")
        click.echo(f"Resume:       {material.resume_path}")
        click.echo(f"Cover letter: {material.cover_letter_path}")
    finally:
        conn.close()


@cli.command()
@click.option("--out", "out_dir", default="materials", show_default=True)
@click.pass_context
def run(ctx, out_dir):
    """Execute the full pipeline (CLI mode requires an LLM extractor for Scout).

    Without a wired extractor, Scout is skipped — use this to re-rank and craft
    from already-scored roles, or use `score` for ad-hoc JDs.
    """
    config, narrative = _load(ctx)
    conn = connect(ctx.obj["db_path"])
    try:
        result = run_pipeline(conn, config, out_dir=out_dir, profile_narrative=narrative)
        click.echo(f"New postings: {result.new_postings}")
        click.echo(f"Scored:       {len(result.evaluations)}")
        click.echo(f"Crafted:      {len(result.crafted)}")
        for err in result.errors:
            click.echo(f"  ! {err}", err=True)
        click.echo("")
        click.echo(report_mod.morning_brief(
            result.evaluations, [c.app_id for c in result.crafted]
        ))
    finally:
        conn.close()


@cli.group()
def track():
    """Manually manage application records."""


@track.command("add")
@click.argument("company")
@click.argument("role")
@click.option("--url", default="")
@click.pass_context
def track_add(ctx, company, role, url):
    """Manually log an application."""
    conn = connect(ctx.obj["db_path"])
    try:
        app = add_application(conn, company, role, url=url)
        click.echo(f"Added #{app.id}: {company} — {role}")
    finally:
        conn.close()


@track.command("update")
@click.argument("app_id", type=int)
@click.argument("new_status")
@click.option("--note", default="")
@click.pass_context
def track_update(ctx, app_id, new_status, note):
    """Update an application's status."""
    conn = connect(ctx.obj["db_path"])
    try:
        try:
            target = ApplicationStatus(new_status.lower())
        except ValueError:
            raise click.ClickException(
                f"Unknown status '{new_status}'. Valid: "
                f"{', '.join(s.value for s in ApplicationStatus)}"
            )
        try:
            app = update_status(conn, app_id, target, note=note)
        except TrackerError as exc:
            raise click.ClickException(str(exc))
        click.echo(f"#{app.id} -> {app.status.value}")
    finally:
        conn.close()


@cli.command()
@click.argument("app_id", type=int)
@click.argument("verdict", type=click.Choice([v.value for v in Verdict]))
@click.option("--reason", default="")
@click.pass_context
def feedback(ctx, app_id, verdict, reason):
    """Log feedback (agree/disagree/skip) on a scored role."""
    import json

    conn = connect(ctx.obj["db_path"])
    try:
        snapshot = []
        row = latest_evaluation_for(conn, app_id)
        if row:
            snapshot = [DimensionScore(**d) for d in json.loads(row["dimension_scores"])]
        log_feedback(conn, app_id, Verdict(verdict), reason=reason, dimension_snapshot=snapshot)
        click.echo(f"Logged {verdict} for app #{app_id}.")
    finally:
        conn.close()


@cli.command()
@click.pass_context
def calibrate(ctx):
    """Review disagreement patterns to inform manual weight adjustments."""
    conn = connect(ctx.obj["db_path"])
    try:
        stats = calibration_stats(conn)
        click.echo(f"Total feedback: {stats['total_feedback']}")
        click.echo(f"Verdicts: {stats['verdict_counts']}")
        disagreements = stats["verdict_counts"].get(Verdict.DISAGREE.value, 0)
        if stats["disagreement_dimension_avgs"]:
            click.echo("\nAvg dimension score at time of disagreement:")
            for key, avg in sorted(stats["disagreement_dimension_avgs"].items(),
                                   key=lambda kv: kv[1]):
                click.echo(f"  {key}: {avg}")
            click.echo(
                "\nDimensions you consistently reject at low scores are candidates "
                "for a weight increase in config.yml."
            )
        elif disagreements:
            click.echo(
                "\nDisagreements logged, but none carry dimension snapshots yet "
                "(snapshots are captured when you give feedback on a scored role)."
            )
        else:
            click.echo("\nNo disagreements logged yet.")
    finally:
        conn.close()


def main() -> None:  # console_scripts entrypoint
    cli(obj={})


if __name__ == "__main__":
    main()
