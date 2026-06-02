"""Read all evaluations and feedback from the DB as JSON. Used by the review artifact."""
import json
import sqlite3
import sys
from pathlib import Path

db_path = Path(__file__).resolve().parent.parent / "applykit.db"
conn = sqlite3.connect(f"file:{db_path}?immutable=1", uri=True)
conn.row_factory = sqlite3.Row

evals = []
for r in conn.execute(
    "SELECT e.app_id, e.company, e.role, e.overall_score, e.grade, "
    "e.dimension_scores, e.recommendation, e.source, a.status "
    "FROM evaluations e JOIN applications a ON e.app_id = a.id "
    "ORDER BY e.overall_score DESC"
).fetchall():
    evals.append({
        "app_id": r["app_id"], "company": r["company"], "role": r["role"],
        "overall": r["overall_score"], "grade": r["grade"],
        "dimensions": json.loads(r["dimension_scores"]),
        "recommendation": r["recommendation"], "url": r["source"],
        "status": r["status"],
    })

fb = []
for r in conn.execute(
    "SELECT app_id, verdict, reason, timestamp FROM feedback ORDER BY id"
).fetchall():
    fb.append({
        "app_id": r["app_id"], "verdict": r["verdict"],
        "reason": r["reason"], "timestamp": r["timestamp"],
    })

conn.close()
print(json.dumps({"evaluations": evals, "feedback": fb}))
