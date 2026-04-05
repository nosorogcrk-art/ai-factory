"""Database and file operations for Skill Tester."""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

DB_PATH = Path("01_ЦЕХ/01_ЖУРНАЛЫ/skill_tester.db")
LOG_DIR = Path("01_ЦЕХ/01_ЖУРНАЛЫ")
LOG_FILE = LOG_DIR / "skill_tester.log"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

def init_db():
    """Initialize SQLite database for test results."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS test_runs (
            test_run_id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            overall TEXT,
            results_json TEXT
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_skill_id ON test_runs(skill_id)')
    conn.commit()
    conn.close()

def save_test_run(test_run_id: str, skill_id: str, started_at: str,
                  finished_at: Optional[str] = None,
                  overall: Optional[str] = None,
                  results: Optional[list] = None):
    """Save test run metadata and results."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT OR REPLACE INTO test_runs
        (test_run_id, skill_id, started_at, finished_at, overall, results_json)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (test_run_id, skill_id, started_at, finished_at, overall,
          json.dumps(results) if results else None))
    conn.commit()
    conn.close()

def get_last_results(skill_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the most recent test results for a skill."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute('''
        SELECT * FROM test_runs
        WHERE skill_id = ?
        ORDER BY started_at DESC
        LIMIT 1
    ''', (skill_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None