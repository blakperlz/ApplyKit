"""Feedback logging and manual calibration.

ADR-001 Tension 5 scopes the MVP to two of the three feedback mechanisms:
disagreement logging and prompt calibration (recent disagreements injected into
the eval prompt). Automated pattern detection / weight suggestion is a fast
follow; :func:`calibration_stats` provides the manual view in the meantime.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Optional

from .models import DimensionScore, FeedbackEntry, Verdict, utc_now_iso


def log_feedback(
    conn: sqlite3.Connection,
    app_id: int,
    verdict: Verdict,
    *,
    reason: str = "",
    dimension_snapshot: Optional[list[DimensionScore]] = None,
) -> int:
    """Record a user verdict (agree/disagree/skip) on a scored role."""
    snapshot = dimension_snapshot or []
    cur = conn.execute(
        "INSERT INTO feedback(app_id, verdict, reason, dimension_snapshot, timestamp) "
        "VALUES(?, ?, ?, ?, ?)",
        (
            app_id,
            verdict.value,
            reason,
            json.dumps([asdict(d) for d in snapshot]),
            utc_now_iso(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def recent_disagreements(conn: sqlite3.Connection, limit: int = 5) -> list[FeedbackEntry]:
    """Most recent DISAGREE entries, newest first — used for prompt calibration."""
    rows = conn.execute(
        "SELECT * FROM feedback WHERE verdict = ? ORDER BY id DESC LIMIT ?",
        (Verdict.DISAGREE.value, limit),
    ).fetchall()
    return [_row_to_feedback(r) for r in rows]


def calibration_examples(conn: sqlite3.Connection, limit: int = 5) -> list[str]:
    """Render recent disagreements as short strings for the evaluation prompt."""
    examples = []
    for fb in recent_disagreements(conn, limit):
        company_role = _describe_app(conn, fb.app_id)
        reason = fb.reason or "(no reason given)"
        examples.append(f"{company_role}: user disagreed — {reason}")
    return examples


def calibration_stats(conn: sqlite3.Connection) -> dict:
    """Aggregate feedback counts. The manual ``applykit calibrate`` view.

    Returns total verdict counts and, for disagreements, the average score per
    dimension at the time of disagreement — the signal a user uses to decide
    whether to reweight a dimension by hand.
    """
    verdict_counts = {
        r["verdict"]: r["n"]
        for r in conn.execute(
            "SELECT verdict, COUNT(*) AS n FROM feedback GROUP BY verdict"
        ).fetchall()
    }

    dim_totals: dict[str, list[float]] = {}
    for r in conn.execute(
        "SELECT dimension_snapshot FROM feedback WHERE verdict = ?",
        (Verdict.DISAGREE.value,),
    ).fetchall():
        for d in json.loads(r["dimension_snapshot"] or "[]"):
            dim_totals.setdefault(d["key"], []).append(float(d["score"]))

    dim_avgs = {
        key: round(sum(vals) / len(vals), 1)
        for key, vals in dim_totals.items()
        if vals
    }
    return {
        "verdict_counts": verdict_counts,
        "disagreement_dimension_avgs": dim_avgs,
        "total_feedback": sum(verdict_counts.values()),
    }


def _describe_app(conn: sqlite3.Connection, app_id: int) -> str:
    row = conn.execute(
        "SELECT company, role FROM applications WHERE id = ?", (app_id,)
    ).fetchone()
    if not row:
        return f"app#{app_id}"
    return f"{row['company']} — {row['role']}"


def _row_to_feedback(row: sqlite3.Row) -> FeedbackEntry:
    snapshot = [
        DimensionScore(**d) for d in json.loads(row["dimension_snapshot"] or "[]")
    ]
    return FeedbackEntry(
        app_id=row["app_id"],
        verdict=Verdict(row["verdict"]),
        reason=row["reason"],
        dimension_snapshot=snapshot,
        timestamp=row["timestamp"],
    )
