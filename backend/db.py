"""Project persistence — SQLite, not the Postgres/Supabase originally sketched
in BUILD_PLAN.md. Zero setup beats a proven-elsewhere pattern for Phase 1:
this needs to be testable immediately, without an external account. Phase 6
(auth, multi-user history, billing) is the natural point to migrate to
Supabase/Postgres if this needs to serve more than one person.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "architect.db")


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def init() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                provider TEXT NOT NULL,
                brief_json TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
            """
        )


def save_project(project_id: str, provider: str, brief: dict, result: dict) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO projects (id, created_at, provider, brief_json, result_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                project_id,
                datetime.now(timezone.utc).isoformat(),
                provider,
                json.dumps(brief),
                json.dumps(result),
            ),
        )


def count_projects() -> int:
    with _connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]


def list_projects(limit: int = 100) -> list[dict]:
    """Lightweight listing - brief only, not the (often large) result, so
    rendering the history table doesn't mean loading every past run's full
    blueprint into memory."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT id, created_at, provider, brief_json FROM projects "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    projects = []
    for project_id, created_at, provider, brief_json in rows:
        brief = json.loads(brief_json)
        projects.append(
            {
                "id": project_id,
                "created_at": created_at,
                "provider": provider,
                "idea": brief.get("idea", ""),
            }
        )
    return projects


def get_project(project_id: str) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT provider, result_json FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
    if row is None:
        return None
    provider, result_json = row
    return {"id": project_id, "provider": provider, **json.loads(result_json)}
