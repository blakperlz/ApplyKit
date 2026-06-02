import pytest

from applykit.models import (
    ApplicationStatus,
    DimensionScore,
    Evaluation,
    can_transition,
    grade_for_score,
    grade_meets_threshold,
    recommendation_for_score,
)


@pytest.mark.parametrize(
    "score,grade",
    [(95, "A"), (90, "A"), (87, "B+"), (85, "B+"), (82, "B"), (75, "C"),
     (65, "D"), (40, "F"), (0, "F"), (100, "A")],
)
def test_grade_for_score(score, grade):
    assert grade_for_score(score) == grade


def test_recommendation_tracks_grade():
    assert recommendation_for_score(91) == "Apply immediately"
    assert recommendation_for_score(86) == "Apply immediately"
    assert recommendation_for_score(81) == "Strong candidate"
    assert recommendation_for_score(72) == "Consider if aligned with goals"
    assert recommendation_for_score(50) == "Skip"


def test_grade_meets_threshold():
    assert grade_meets_threshold("A", "B+")
    assert grade_meets_threshold("B+", "B+")
    assert not grade_meets_threshold("B", "B+")
    assert grade_meets_threshold("B", "C")


def test_status_transitions_legal_and_illegal():
    assert can_transition(ApplicationStatus.NEW, ApplicationStatus.SCORED)
    assert can_transition(ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEWING)
    assert can_transition(ApplicationStatus.OFFERED, ApplicationStatus.ACCEPTED)
    # illegal: cannot jump from NEW straight to OFFERED
    assert not can_transition(ApplicationStatus.NEW, ApplicationStatus.OFFERED)
    # terminal states go nowhere
    assert not can_transition(ApplicationStatus.ACCEPTED, ApplicationStatus.APPLIED)


def test_evaluation_weighted_overall_and_grade():
    dims = [
        DimensionScore("role_fit", "Role Fit", score=100, weight=60),
        DimensionScore("technical_match", "Technical Match", score=50, weight=40),
    ]
    ev = Evaluation.from_dimension_scores("Acme", "Director", dims)
    # (100*60 + 50*40) / 100 = 80
    assert ev.overall_score == 80.0
    assert ev.grade == "B"
    assert ev.recommendation == "Strong candidate"


def test_evaluation_weights_normalised_when_not_100():
    dims = [
        DimensionScore("a", "A", score=90, weight=3),
        DimensionScore("b", "B", score=90, weight=1),
    ]
    ev = Evaluation.from_dimension_scores("Acme", "Role", dims)
    assert ev.overall_score == 90.0  # normalisation, not sum


def test_evaluation_zero_weight_is_safe():
    dims = [DimensionScore("a", "A", score=90, weight=0)]
    ev = Evaluation.from_dimension_scores("Acme", "Role", dims)
    assert ev.overall_score == 0.0
