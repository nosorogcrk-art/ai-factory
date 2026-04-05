import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
import os

logger = logging.getLogger(__name__)

DB_PATH = Path("01_ЦЕХ/01_ЖУРНАЛЫ/test_stand.db")
MAX_JOBS = int(os.getenv("MAX_JOBS", "1000"))

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            product_path TEXT NOT NULL,
            test_suite TEXT NOT NULL,
            image TEXT NOT NULL,
            timeout_seconds INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            finished_at TEXT,
            report_file TEXT,
            error TEXT
        )
    ''')
    conn.execute('''
        DELETE FROM jobs WHERE job_id NOT IN (
            SELECT job_id FROM jobs ORDER BY started_at DESC LIMIT ?
        )
    ''', (MAX_JOBS,))
    conn.commit()
    conn.close()

def save_job(job: Dict[str, Any]):
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        INSERT OR REPLACE INTO jobs (
            job_id, product_path, test_suite, image, timeout_seconds,
            status, started_at, finished_at, report_file, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        job["job_id"],
        job["product_path"],
        job["test_suite"],
        job["image"],
        job["timeout_seconds"],
        job["status"],
        job.get("started_at"),
        job.get("finished_at"),
        job.get("report_file"),
        job.get("error")
    ))
    conn.commit()
    conn.close()

def load_job(job_id: str) -> Optional[Dict[str, Any]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def delete_old_jobs():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        DELETE FROM jobs WHERE job_id NOT IN (
            SELECT job_id FROM jobs ORDER BY started_at DESC LIMIT ?
        )
    ''', (MAX_JOBS,))
    conn.commit()
    conn.close()