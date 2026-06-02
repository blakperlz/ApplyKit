"""Markdown report generation. Pure string builders over evaluations and summaries."""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import Evaluation
from .ranking import rank


def evaluation_detail(evaluation: Evaluation) -> str:
    """A full breakdown for one role: overall grade plus every dimension."""
    lines = [
        f"# {evaluation.company} — {evaluation.role}",
        "",
        f"**Overall:** {evaluation.overall_score:g}/100 "
        f"(**{evaluation.grade}**) — {evaluation.recommendation}",
        "",
        "| Dimension | Score | Weight | Why |",
        "| --- | ---: | ---: | --- |",
    ]
    for d in evaluation.dimension_scores:
        why = d.explanation.replace("\n", " ").replace("|", "\\|")
        lines.append(f"| {d.label} | {d.score:g} | {d.weight:g}% | {why} |")
    if evaluation.source:
        lines += ["", f"_Source: {evaluation.source}_"]
    return "\n".join(lines)


def ranked_table(evaluations: Iterable[Evaluation]) -> str:
    """A leaderboard of all scored roles, best first."""
    ranked = rank(evaluations)
    lines = [
        "# Ranked roles",
        "",
        "| # | Company | Role | Score | Grade | Recommendation |",
        "| ---: | --- | --- | ---: | :---: | --- |",
    ]
    for i, e in enumerate(ranked, start=1):
        lines.append(
            f"| {i} | {e.company} | {e.role} | {e.overall_score:g} | "
            f"{e.grade} | {e.recommendation} |"
        )
    if not ranked:
        lines.append("| — | _no roles scored yet_ | | | | |")
    return "\n".join(lines)


def status_summary(counts: Mapping[str, int]) -> str:
    """Pipeline overview from a status->count map (see tracker.summary)."""
    lines = ["# Pipeline summary", "", "| Status | Count |", "| --- | ---: |"]
    if not counts:
        lines.append("| _no applications_ | 0 |")
    else:
        for status, n in sorted(counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {status} | {n} |")
        lines += ["", f"**Total:** {sum(counts.values())}"]
    return "\n".join(lines)


def morning_brief(
    evaluations: Iterable[Evaluation], crafted_app_ids: Iterable[int] = ()
) -> str:
    """The 'what you wake up to' report: ranked roles + which have materials ready."""
    ranked = rank(evaluations)
    crafted = set(crafted_app_ids)
    lines = [
        "# ApplyKit — this morning's results",
        "",
        f"{len(ranked)} role(s) scored. "
        f"{len(crafted)} with materials ready to review.",
        "",
    ]
    for i, e in enumerate(ranked, start=1):
        ready = " ✅ materials ready" if e.app_id in crafted else ""
        lines.append(
            f"{i}. **{e.company} — {e.role}** · {e.overall_score:g} "
            f"(**{e.grade}**) — {e.recommendation}{ready}"
        )
    if not ranked:
        lines.append("_Nothing new overnight._")
    return "\n".join(lines)
