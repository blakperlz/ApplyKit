"""Core data types: enums, dataclasses, the grade scale, and the status machine.

This module imports nothing from the rest of the package. It is the bottom of
the dependency graph and defines the shapes that every other module passes
around and that :mod:`applykit.db` persists.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #

class CompanyTier(str, Enum):
    """Priority tier for a monitored company. Dream companies are scored first."""

    DREAM = "dream"
    TARGET = "target"
    OPPORTUNISTIC = "opportunistic"


class Verdict(str, Enum):
    """User's reaction to a scored role during the Apply step."""

    AGREE = "agree"
    DISAGREE = "disagree"
    SKIP = "skip"


class ApplicationStatus(str, Enum):
    """Lifecycle state of an application. Transitions are governed below."""

    NEW = "new"
    SCORED = "scored"
    CRAFTED = "crafted"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    WITHDRAWN = "withdrawn"


# Allowed status transitions. A transition not listed here is rejected by the
# tracker. Terminal states map to an empty set.
STATUS_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.NEW: {ApplicationStatus.SCORED, ApplicationStatus.SKIPPED},
    ApplicationStatus.SCORED: {
        ApplicationStatus.CRAFTED,
        ApplicationStatus.APPLIED,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.CRAFTED: {
        ApplicationStatus.APPLIED,
        ApplicationStatus.SKIPPED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.APPLIED: {
        ApplicationStatus.INTERVIEWING,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEWING: {
        ApplicationStatus.OFFERED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFERED: {
        ApplicationStatus.ACCEPTED,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.ACCEPTED: set(),
    ApplicationStatus.REJECTED: set(),
    ApplicationStatus.SKIPPED: set(),
    ApplicationStatus.WITHDRAWN: set(),
}

TERMINAL_STATUSES = frozenset(
    s for s, nxt in STATUS_TRANSITIONS.items() if not nxt
)


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    """True if ``current -> target`` is a permitted status change."""
    return target in STATUS_TRANSITIONS.get(current, set())


# --------------------------------------------------------------------------- #
# Grade scale (PRD section 4, Step 2)
# --------------------------------------------------------------------------- #

# Ordered high-to-low. Each entry: (label, min_score_inclusive, recommendation).
_GRADE_SCALE: list[tuple[str, float, str]] = [
    ("A", 90.0, "Apply immediately"),
    ("B+", 85.0, "Apply immediately"),
    ("B", 80.0, "Strong candidate"),
    ("C", 70.0, "Consider if aligned with goals"),
    ("D", 60.0, "Skip"),
    ("F", 0.0, "Skip"),
]


def grade_for_score(score: float) -> str:
    """Return the letter grade label for an overall score in ``[0, 100]``."""
    for label, threshold, _rec in _GRADE_SCALE:
        if score >= threshold:
            return label
    return "F"


def recommendation_for_score(score: float) -> str:
    """Return the human recommendation string for an overall score."""
    for _label, threshold, rec in _GRADE_SCALE:
        if score >= threshold:
            return rec
    return "Skip"


# Grade rank for comparisons such as "meets the craft threshold". Higher is
# better. Used so a configurable threshold like "B+" can be compared.
GRADE_RANK: dict[str, int] = {
    "F": 0,
    "D": 1,
    "C": 2,
    "B": 3,
    "B+": 4,
    "A": 5,
}


def grade_meets_threshold(grade: str, threshold: str) -> bool:
    """True if ``grade`` is at least as good as ``threshold`` (e.g. B+ >= B)."""
    return GRADE_RANK.get(grade, -1) >= GRADE_RANK.get(threshold, 99)


def utc_now_iso() -> str:
    """Current UTC time as an ISO-8601 string (the storage format for timestamps)."""
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------- #
# Dataclasses
# --------------------------------------------------------------------------- #

@dataclass
class Dimension:
    """A single scoring dimension and its weight (a percentage, e.g. 20.0)."""

    key: str
    label: str
    weight: float
    description: str = ""


@dataclass
class DimensionScore:
    """The evaluator's score and rationale for one dimension of one JD."""

    key: str
    label: str
    score: float          # 0-100
    weight: float         # percentage applied
    explanation: str = ""


@dataclass
class Evaluation:
    """The full scoring result for one job description."""

    company: str
    role: str
    overall_score: float
    grade: str
    dimension_scores: list[DimensionScore] = field(default_factory=list)
    recommendation: str = ""
    source: str = ""                       # URL, file path, or "text"
    raw_jd: str = ""
    evaluated_at: str = field(default_factory=utc_now_iso)
    app_id: Optional[int] = None

    @classmethod
    def from_dimension_scores(
        cls,
        company: str,
        role: str,
        dimension_scores: list[DimensionScore],
        **kwargs,
    ) -> "Evaluation":
        """Build an Evaluation, computing the weighted overall score and grade.

        Overall = sum(score * weight) / sum(weight), so weights need not total
        exactly 100 — they are normalised here.
        """
        total_weight = sum(d.weight for d in dimension_scores)
        if total_weight <= 0:
            overall = 0.0
        else:
            overall = sum(d.score * d.weight for d in dimension_scores) / total_weight
        overall = round(overall, 1)
        return cls(
            company=company,
            role=role,
            overall_score=overall,
            grade=grade_for_score(overall),
            dimension_scores=dimension_scores,
            recommendation=recommendation_for_score(overall),
            **kwargs,
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Posting:
    """A job listing seen by Scout. Identity is the URL hash within a company."""

    company: str
    title: str
    url: str
    url_hash: str = ""
    first_seen: str = field(default_factory=utc_now_iso)


@dataclass
class Application:
    """A tracked application record."""

    company: str
    role: str
    url: str = ""
    status: ApplicationStatus = ApplicationStatus.NEW
    created_at: str = field(default_factory=utc_now_iso)
    id: Optional[int] = None


@dataclass
class FeedbackEntry:
    """A user verdict on a scored role, with the dimension scores captured."""

    app_id: int
    verdict: Verdict
    reason: str = ""
    dimension_snapshot: list[DimensionScore] = field(default_factory=list)
    timestamp: str = field(default_factory=utc_now_iso)


@dataclass
class CraftedMaterial:
    """File paths to generated application materials for one role."""

    app_id: int
    resume_path: str = ""
    cover_letter_path: str = ""
    crafted_at: str = field(default_factory=utc_now_iso)
