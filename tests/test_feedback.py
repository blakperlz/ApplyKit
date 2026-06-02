from applykit.feedback import (
    calibration_examples,
    calibration_stats,
    log_feedback,
    recent_disagreements,
)
from applykit.models import DimensionScore, Verdict
from applykit.tracker import add_application


def _snapshot(role_fit_score):
    return [
        DimensionScore("role_fit", "Role Fit", score=role_fit_score, weight=60),
        DimensionScore("technical_match", "Technical Match", score=80, weight=40),
    ]


def test_log_and_recent_disagreements(conn):
    app = add_application(conn, "Acme", "Director")
    log_feedback(conn, app.id, Verdict.DISAGREE, reason="too junior",
                 dimension_snapshot=_snapshot(40))
    log_feedback(conn, app.id, Verdict.AGREE)
    dis = recent_disagreements(conn, limit=5)
    assert len(dis) == 1
    assert dis[0].reason == "too junior"
    assert dis[0].dimension_snapshot[0].score == 40


def test_calibration_examples_render_company_and_reason(conn):
    app = add_application(conn, "Acme", "Director")
    log_feedback(conn, app.id, Verdict.DISAGREE, reason="comp too low",
                 dimension_snapshot=_snapshot(30))
    examples = calibration_examples(conn, limit=5)
    assert len(examples) == 1
    assert "Acme" in examples[0]
    assert "comp too low" in examples[0]


def test_calibration_stats_aggregates(conn):
    app = add_application(conn, "Acme", "Director")
    log_feedback(conn, app.id, Verdict.DISAGREE, dimension_snapshot=_snapshot(40))
    log_feedback(conn, app.id, Verdict.DISAGREE, dimension_snapshot=_snapshot(60))
    log_feedback(conn, app.id, Verdict.SKIP)
    stats = calibration_stats(conn)
    assert stats["total_feedback"] == 3
    assert stats["verdict_counts"]["disagree"] == 2
    # avg role_fit at disagreement = (40+60)/2 = 50
    assert stats["disagreement_dimension_avgs"]["role_fit"] == 50.0


def test_recent_disagreements_limit(conn):
    app = add_application(conn, "Acme", "Director")
    for i in range(7):
        log_feedback(conn, app.id, Verdict.DISAGREE, reason=f"r{i}",
                     dimension_snapshot=_snapshot(50))
    assert len(recent_disagreements(conn, limit=5)) == 5
