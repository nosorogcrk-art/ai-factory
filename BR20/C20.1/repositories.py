import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = Path(os.getenv("DB_PATH", "/data/gitops.db"))

def get_connection():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS deployments (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            repo_url TEXT NOT NULL,
            branch TEXT NOT NULL,
            version TEXT,
            log TEXT
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_deployments_status ON deployments (status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_deployments_started_at ON deployments (started_at)')
    conn.commit()
    conn.close()

def save_deployment(deployment: Dict[str, Any]):
    conn = get_connection()
    conn.execute('''
        INSERT OR REPLACE INTO deployments (
            id, status, started_at, finished_at, repo_url, branch, version, log
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        deployment["id"],
        deployment["status"],
        deployment["started_at"],
        deployment.get("finished_at"),
        deployment["repo_url"],
        deployment["branch"],
        deployment.get("version"),
        deployment.get("log")
    ))
    conn.commit()
    conn.close()

def get_deployment(deployment_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM deployments WHERE id = ?", (deployment_id,)).fetchone()
    conn.close()
    return dict(row) if row else None

def list_deployments(limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    conn = get_connection()
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM deployments ORDER BY started_at DESC LIMIT ? OFFSET ?",
        (limit, offset)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]