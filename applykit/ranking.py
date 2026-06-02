"""Ranking and filtering over a set of evaluations. Pure functions, no IO."""

from __future__ import annotations

from typing import Iterable, Optional

from .models import Evaluation, grade_meets_threshold


def rank(evaluations: Iterable[Evaluation]) -> list[Evaluation]:
    """Return evaluations sorted best-first by overall score (ties: company name)."""
    return sorted(
        evaluations,
        key=lambda e: (-e.overall_score, e.company.lower(), e.role.lower()),
    )


def filter_by_grade(
    evaluations: Iterable[Evaluation], min_grade: str
) -> list[Evaluation]:
    """Keep evaluations whose grade is at least ``min_grade`` (e.g. 'B+')."""
    return [e for e in evaluations if grade_meets_threshold(e.grade, min_grade)]


def filter_by(
    evaluations: Iterable[Evaluation],
    *,
    company: Optional[str] = None,
    min_score: Optional[float] = None,
    max_score: Optional[float] = None,
) -> list[Evaluation]:
    """Filter by company (case-insensitive) and/or score range."""
    out = []
    for e in evaluations:
        if company and e.company.lower() != company.lower():
            continue
        if min_score is not None and e.overall_score < min_score:
            continue
        if max_score is not None and e.overall_score > max_score:
            continue
        out.append(e)
    return out


def select_for_craft(
    evaluations: Iterable[Evaluation],
    *,
    threshold: str,
    cap: int,
    company_threshold=None,
) -> list[Evaluation]:
    """Pick which roles get materials this run.

    Applies the craft threshold (a grade, configurable per company via
    ``company_threshold(company) -> grade``), then ranks and takes the top
    ``cap``. Implements the PRD volume controls: if 12 roles qualify but cap is
    5, only the top 5 win the slots.
    """
    qualifying = []
    for e in evaluations:
        eff_threshold = threshold
        if company_threshold is not None:
            eff_threshold = company_threshold(e.company) or threshold
        if grade_meets_threshold(e.grade, eff_threshold):
            qualifying.append(e)
    ranked = rank(qualifying)
    if cap is not None and cap >= 0:
        return ranked[:cap]
    return ranked
