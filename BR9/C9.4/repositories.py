import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path("/data/dialogue_sessions.db")
TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            history TEXT NOT NULL,
            collected_data TEXT,
            status TEXT DEFAULT 'active'
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions (project_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_sessions_id ON sessions (session_id)')
    conn.commit()
    conn.close()

def get_session(session_id: str) -> Tuple[list, dict]:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT history, collected_data FROM sessions WHERE session_id = ?", (session_id,))
        row = cur.fetchone()
        if row:
            return json.loads(row[0]), json.loads(row[1]) if row[1] else {}
    return [], {}

def save_session(session_id: str, project_id: str, history: list, collected_data: dict = None):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO sessions (session_id, project_id, created_at, updated_at, history, collected_data, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (session_id, project_id, datetime.now(timezone.utc).isoformat(),
             datetime.now(timezone.utc).isoformat(),
             json.dumps(history, ensure_ascii=False),
             json.dumps(collected_data) if collected_data else None,
             'active')
        )
        conn.commit()

def update_task_status(task_id: str, status: str, history_entry: str = None):
    try:
        with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
            registry = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        registry = []

    updated = False
    for task in registry:
        if task.get("id") == task_id:
            task["status"] = status
            if history_entry:
                task.setdefault("history", []).append(history_entry)
            updated = True
            break

    if not updated:
        logger.error(f"Task {task_id} not found in registry")
        return

    with open(TASK_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    logger.info(f"Task {task_id} status updated to {status}")