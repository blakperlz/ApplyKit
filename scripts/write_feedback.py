"""Write a feedback entry to the DB. Used by the review artifact.

Handles mounted-filesystem SQLite issues by copying the DB to /tmp for writes,
then copying back.

Usage: python write_feedback.py <app_id> <verdict> [reason]
"""
import json
import shutil
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from applykit.models import utc_now_iso

app_id = int(sys.argv[1])
verdict = sys.argv[2]
reason = sys.argv[3] if len(sys.argv) > 3 else ""

db_path = Path(__file__).resolve().parent.parent / "applykit.db"
tmp_path = Path("/tmp/applykit_write.db")

# Copy to /tmp for safe writes
shutil.copy2(str(db_path), str(tmp_path))

conn = sqlite3.connect(str(tmp_path))
conn.row_factory = sqlite3.Row

ev = conn.execute(
    "SELECT dimension_scores FROM evaluations WHERE app_id=?", (app_id,)
).fetchone()
snap = ev["dimension_scores"] if ev else "[]"

conn.execute(
    "INSERT INTO feedback(app_id, verdict, reason, dimension_snapshot, timestamp) "
    "VALUES(?, ?, ?, ?, ?)",
    (app_id, verdict, reason, snap, utc_now_iso()),
)
conn.commit()
conn.close()

# Copy back
shutil.copy2(str(tmp_path), str(db_path))
tmp_path.unlink(missing_ok=True)

print(json.dumps({"status": "ok", "app_id": app_id, "verdict": verdict}))
