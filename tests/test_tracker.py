import pytest

from applykit.models import ApplicationStatus, DimensionScore, Evaluation
from applykit.tracker import (
    TrackerError,
    add_application,
    get_application,
    latest_evaluation_for,
    list_applications,
    save_evaluation,
    status_history,
    summary,
    update_status,
)


def test_add_and_get_application(conn):
    app = add_application(conn, "Acme", "Director", url="http://x")
    assert app.id is not None
    fetched = get_application(conn, app.id)
    assert fetched.company == "Acme"
    assert fetched.status == ApplicationStatus.NEW


def test_add_seeds_status_history(conn):
    app = add_application(conn, "Acme", "Director")
    history = status_history(conn, app.id)
    assert len(history) == 1
    assert history[0]["to_status"] == "new"


def test_legal_transition_updates_and_logs(conn):
    app = add_application(conn, "Acme", "Director")
    update_status(conn, app.id, ApplicationStatus.SCORED)
    update_status(conn, app.id, ApplicationStatus.APPLIED, note="sent")
    fetched = get_application(conn, app.id)
    assert fetched.status == ApplicationStatus.APPLIED
    history = status_history(conn, app.id)
    assert [h["to_status"] for h in history] == ["new", "scored", "applied"]
    assert history[-1]["note"] == "sent"


def test_illegal_transition_raises(conn):
    app = add_application(conn, "Acme", "Director")
    with pytest.raises(TrackerError):
        update_status(conn, app.id, ApplicationStatus.OFFERED)


def test_update_unknown_app_raises(conn):
    with pytest.raises(TrackerError):
        update_status(conn, 999, ApplicationStatus.SCORED)


def test_same_status_is_idempotent(conn):
    app = add_application(conn, "Acme", "Director")
    update_status(conn, app.id, ApplicationStatus.NEW)  # no-op, no raise
    assert len(status_history(conn, app.id)) == 1


def test_save_and_fetch_evaluation(conn):
    app = add_application(conn, "Acme", "Director")
    dims = [DimensionScore("role_fit", "Role Fit", score=90, weight=100)]
    ev = Evaluation.from_dimension_scores("Acme", "Director", dims, app_id=app.id)
    save_evaluation(conn, ev, app_id=app.id)
    row = latest_evaluation_for(conn, app.id)
    assert row["grade"] == "A"
    assert row["overall_score"] == 90.0


def test_summary_counts_by_status(conn):
    a = add_application(conn, "A", "r")
    add_application(conn, "B", "r")
    update_status(conn, a.id, ApplicationStatus.SCORED)
    counts = summary(conn)
    assert counts.get("new") == 1
    assert counts.get("scored") == 1


def test_list_filter_by_status(conn):
    a = add_application(conn, "A", "r")
    add_application(conn, "B", "r")
    update_status(conn, a.id, ApplicationStatus.SCORED)
    scored = list_applications(conn, status=ApplicationStatus.SCORED)
    assert len(scored) == 1
    assert scored[0].company == "A"
