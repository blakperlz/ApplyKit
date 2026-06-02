"""Application tracker: CRUD over the applications table plus the status machine.

Every status change is validated against :data:`models.STATUS_TRANSITIONS` and
recorded in ``status_history`` for an audit trail. Evaluations and crafted
materials are persisted here too so the tracker is the one writer of record.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from typing import Optional

from .models import (
    Application,
    ApplicationStatus,
    CraftedMaterial,
    Evaluation,
    can_transition,
    utc_now_iso,
)


class TrackerError(Exception):
    """Raised on invalid status transitions or missing records."""


# --------------------------------------------------------------------------- #
# Applications
# --------------------------------------------------------------------------- #

def add_application(
    conn: sqlite3.Connection,
    company: str,
    role: str,
    *,
    url: str = "",
    status: ApplicationStatus = ApplicationStatus.NEW,
) -> Application:
    """Insert a new application and seed its status history."""
    created = utc_now_iso()
    cur = conn.execute(
        "INSERT INTO applications(company, role, url, status, created_at) "
        "VALUES(?, ?, ?, ?, ?)",
        (company, role, url, status.value, created),
    )
    app_id = cur.lastrowid
    conn.execute(
        "INSERT INTO status_history(app_id, from_status, to_status, note, timestamp) "
        "VALUES(?, ?, ?, ?, ?)",
        (app_id, None, status.value, "created", created),
    )
    conn.commit()
    return Application(
        id=app_id, company=company, role=role, url=url, status=status, created_at=created
    )


def get_application(conn: sqlite3.Connection, app_id: int) -> Optional[Application]:
    row = conn.execute(
        "SELECT * FROM applications WHERE id = ?", (app_id,)
    ).fetchone()
    return _row_to_application(row) if row else None


def list_applications(
    conn: sqlite3.Connection, *, status: Optional[ApplicationStatus] = None
) -> list[Application]:
    if status is not None:
        rows = conn.execute(
            "SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC",
            (status.value,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM applications ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_application(r) for r in rows]


def update_status(
    conn: sqlite3.Connection,
    app_id: int,
    target: ApplicationStatus,
    *,
    note: str = "",
) -> Application:
    """Transition an application to ``target`` if the move is legal.

    Raises :class:`TrackerError` for unknown apps or disallowed transitions.
    """
    app = get_application(conn, app_id)
    if app is None:
        raise TrackerError(f"No application with id {app_id}.")
    if app.status == target:
        return app  # idempotent no-op
    if not can_transition(app.status, target):
        raise TrackerError(
            f"Illegal transition {app.status.value} -> {target.value} "
            f"for application {app_id}."
        )
    ts = utc_now_iso()
    conn.execute("UPDATE applications SET status = ? WHERE id = ?", (target.value, app_id))
    conn.execute(
        "INSERT INTO status_history(app_id, from_status, to_status, note, timestamp) "
        "VALUES(?, ?, ?, ?, ?)",
        (app_id, app.status.value, target.value, note, ts),
    )
    conn.commit()
    app.status = target
    return app


def status_history(conn: sqlite3.Connection, app_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT from_status, to_status, note, timestamp FROM status_history "
        "WHERE app_id = ? ORDER BY id ASC",
        (app_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Evaluations
# --------------------------------------------------------------------------- #

def save_evaluation(
    conn: sqlite3.Connection,
    evaluation: Evaluation,
    *,
    app_id: Optional[int] = None,
) -> int:
    """Persist an evaluation (optionally linked to an application). Returns its id."""
    dim_json = json.dumps([asdict(d) for d in evaluation.dimension_scores])
    cur = conn.execute(
        "INSERT INTO evaluations(app_id, company, role, overall_score, grade, "
        "dimension_scores, recommendation, source, raw_jd, evaluated_at) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            app_id if app_id is not None else evaluation.app_id,
            evaluation.company,
            evaluation.role,
            evaluation.overall_score,
            evaluation.grade,
            dim_json,
            evaluation.recommendation,
            evaluation.source,
            evaluation.raw_jd,
            evaluation.evaluated_at,
        ),
    )
    conn.commit()
    return cur.lastrowid


def latest_evaluation_for(conn: sqlite3.Connection, app_id: int) -> Optional[dict]:
    row = conn.execute(
        "SELECT * FROM evaluations WHERE app_id = ? ORDER BY id DESC LIMIT 1",
        (app_id,),
    ).fetchone()
    return dict(row) if row else None


# --------------------------------------------------------------------------- #
# Crafted materials
# --------------------------------------------------------------------------- #

def save_materials(conn: sqlite3.Connection, material: CraftedMaterial) -> int:
    cur = conn.execute(
        "INSERT INTO crafted_materials(app_id, resume_path, cover_letter_path, crafted_at) "
        "VALUES(?, ?, ?, ?)",
        (material.app_id, material.resume_path, material.cover_letter_path, material.crafted_at),
    )
    conn.commit()
    return cur.lastrowid


# --------------------------------------------------------------------------- #
# Pipeline summary
# --------------------------------------------------------------------------- #

def summary(conn: sqlite3.Connection) -> dict[str, int]:
    """Count of applications by status — the data behind ``applykit status``."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM applications GROUP BY status"
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def _row_to_application(row: sqlite3.Row) -> Application:
    return Application(
        id=row["id"],
        company=row["company"],
        role=row["role"],
        url=row["url"],
        status=ApplicationStatus(row["status"]),
        created_at=row["created_at"],
    )
