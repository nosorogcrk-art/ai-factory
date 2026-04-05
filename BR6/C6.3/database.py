import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from models import CostReport

DB_PATH = Path("/data/costs.db")
logger = logging.getLogger(__name__)

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS cost_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            agent TEXT,
            task_id TEXT,
            branch TEXT,
            model TEXT,
            prompt_tokens INTEGER,
            completion_tokens INTEGER,
            cost_usd REAL,
            success INTEGER,
            duration_ms INTEGER
        )
    ''')
    conn.commit()
    conn.close()
    logger.info("Database initialized")

def insert_report(report: CostReport):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO cost_logs (
            timestamp, agent, task_id, branch, model,
            prompt_tokens, completion_tokens, cost_usd, success, duration_ms
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        report.timestamp.isoformat(),
        report.agent,
        report.task_id,
        report.branch,
        report.model,
        report.prompt_tokens,
        report.completion_tokens,
        report.cost_usd,
        1 if report.success else 0,
        report.duration_ms
    ))
    conn.commit()
    conn.close()
    logger.info(f"Inserted report for {report.agent} ({report.model}): ${report.cost_usd}")

def get_total_cost_since(since: datetime) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(cost_usd) FROM cost_logs WHERE timestamp >= ?", (since.isoformat(),))
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def get_agent_cost(agent: str, since: datetime) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(cost_usd) FROM cost_logs WHERE agent = ? AND timestamp >= ?", (agent, since.isoformat()))
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total

def get_branch_cost(branch: str, since: datetime) -> float:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT SUM(cost_usd) FROM cost_logs WHERE branch = ? AND timestamp >= ?", (branch, since.isoformat()))
    total = cursor.fetchone()[0] or 0.0
    conn.close()
    return total
