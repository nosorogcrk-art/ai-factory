import os
import json
import logging
import sqlite3
import uuid
import asyncio
import httpx
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

# --- Конфигурация ---
DB_PATH = Path(os.getenv("DB_PATH", "/data/skill_updater.db"))
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/skill_updater.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Переменные окружения ---
LOG_ANALYZER_URL = os.getenv("LOG_ANALYZER_URL", "http://log-analyzer:8101")
SKILL_REGISTRY_URL = os.getenv("SKILL_REGISTRY_URL", "http://skill-registry:8088")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

# --- SQLite инициализация ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS improvement_jobs (
            job_id TEXT PRIMARY KEY,
            skill_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            result TEXT,
            parameters TEXT,
            attempts INTEGER DEFAULT 0
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS improvement_proposals (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            original_skill TEXT,
            improved_skill TEXT,
            version TEXT,
            created_at TEXT NOT NULL,
            approved_at TEXT,
            FOREIGN KEY (job_id) REFERENCES improvement_jobs (job_id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_improvement_jobs_skill_id ON improvement_jobs (skill_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_improvement_jobs_created_at ON improvement_jobs (created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_improvement_jobs_status ON improvement_jobs (status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_improvement_proposals_job_id ON improvement_proposals (job_id)')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_PATH)

class ImproveRequest(BaseModel):
    goals: Optional[List[str]] = None
    num_variants: int = Field(1, ge=1, le=5)

app = FastAPI(title="Skill Updater", version="0.3.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

# --- Отправка логов в BR18 (без background_tasks) ---
async def send_log_to_br18(event_type: str, details: dict) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as http_client:
            await http_client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": "C19.3",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
            logger.info(f"Log sent to BR18: {event_type}")
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

@app.on_event("startup")
async def startup():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT job_id, skill_id, parameters, attempts FROM improvement_jobs WHERE status = 'pending' AND attempts < 3")
        rows = cur.fetchall()
        for job_id, skill_id, params_json, attempts in rows:
            params = json.loads(params_json) if params_json else {}
            goals = params.get("goals", [])
            num_variants = params.get("num_variants", 1)
            logger.info(f"Recovering pending job {job_id} (attempt {attempts+1})")
            asyncio.create_task(run_improvement(job_id, skill_id, goals, num_variants, attempts+1))

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Получение навыка из skill-registry (C17.1) ---
async def fetch_skill(skill_id: str) -> dict:
    try:
        resp = await client.get(f"{SKILL_REGISTRY_URL}/skills/{skill_id}")
        if resp.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Skill {skill_id} not found")
        resp.raise_for_status()
        return resp.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch skill {skill_id}: {e}")
        raise HTTPException(status_code=503, detail=f"Could not fetch skill: {e}")

# --- Получение проблем из Log Analyzer ---
async def fetch_issues_from_log_analyzer() -> dict:
    try:
        resp = await client.get(f"{LOG_ANALYZER_URL}/clusters?limit=10")
        resp.raise_for_status()
        clusters = resp.json().get("clusters", [])
        resp2 = await client.get(f"{LOG_ANALYZER_URL}/patterns?limit=10")
        resp2.raise_for_status()
        patterns = resp2.json().get("patterns", [])
        return {"clusters": clusters, "patterns": patterns}
    except Exception as e:
        logger.warning(f"Failed to fetch issues from Log Analyzer: {e}")
        return {"clusters": [], "patterns": []}

# --- Генерация улучшенной версии навыка (заглушка LLM) ---
async def generate_improved_skill(skill_id: str, original_skill: dict, issues: dict, goals: List[str]) -> str:
    logger.info(f"Generating improved skill for {skill_id} (stub)")
    name = original_skill.get("name", skill_id)
    description = original_skill.get("description", "")
    prompt = original_skill.get("prompt", "")
    improved = f"[STUB] Improved version for {name}\n\nOriginal description: {description}\n\nOriginal prompt: {prompt[:200]}...\n\nIssues from logs: {json.dumps(issues)[:500]}\n\nGoals: {goals}"
    return improved

# --- Обновление навыка в skill-registry ---
async def update_skill_in_registry(skill_id: str, new_skill_data: dict) -> bool:
    try:
        resp = await client.put(f"{SKILL_REGISTRY_URL}/skills/{skill_id}", json=new_skill_data)
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to update skill {skill_id}: {e}")
        return False

# --- Проверка отмены ---
async def is_job_cancelled(job_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM improvement_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return row and row[0] == 'cancelled'

# --- Фоновая задача улучшения ---
async def run_improvement(job_id: str, skill_id: str, goals: List[str], num_variants: int, attempt: int = 1):
    logger.info(f"Improvement job {job_id} started for skill {skill_id} (attempt {attempt})")
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            if await is_job_cancelled(job_id):
                logger.info(f"Job {job_id} cancelled before execution")
                cur.execute(
                    "UPDATE improvement_jobs SET status = 'cancelled', completed_at = ?, result = ? WHERE job_id = ?",
                    (datetime.now(timezone.utc).isoformat(), json.dumps({"message": "cancelled"}), job_id)
                )
                conn.commit()
                return

            skill = await fetch_skill(skill_id)
            issues = await fetch_issues_from_log_analyzer()
            improved_text = await generate_improved_skill(skill_id, skill, issues, goals)

            current_version = skill.get("version", "1.0.0")
            parts = current_version.split('.')
            try:
                major, minor, patch = map(int, parts[:3])
                new_version = f"{major}.{minor}.{patch+1}"
            except Exception:
                new_version = "2.0.0"

            proposal_id = f"prop_{uuid.uuid4().hex[:8]}"
            cur.execute(
                "INSERT INTO improvement_proposals (id, job_id, skill_id, original_skill, improved_skill, version, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (proposal_id, job_id, skill_id, json.dumps(skill), improved_text, new_version, datetime.now(timezone.utc).isoformat())
            )

            cur.execute(
                "UPDATE improvement_jobs SET status = 'completed', completed_at = ?, result = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(),
                 json.dumps({"proposal_id": proposal_id, "message": "Improvement completed"}),
                 job_id)
            )
            conn.commit()
            logger.info(f"Improvement job {job_id} completed, proposal {proposal_id}")
            asyncio.create_task(send_log_to_br18("improvement_completed", {"job_id": job_id, "skill_id": skill_id, "proposal_id": proposal_id}))
        except HTTPException as e:
            logger.error(f"Improvement job {job_id} failed with HTTPException: {e.detail}")
            cur.execute(
                "UPDATE improvement_jobs SET status = 'failed', completed_at = ?, result = ?, attempts = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(), json.dumps({"error": e.detail}), attempt, job_id)
            )
            conn.commit()
            asyncio.create_task(send_log_to_br18("improvement_failed", {"job_id": job_id, "skill_id": skill_id, "error": str(e.detail)}))
        except Exception as e:
            logger.error(f"Improvement job {job_id} failed: {e}")
            cur.execute(
                "UPDATE improvement_jobs SET status = 'failed', completed_at = ?, result = ?, attempts = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(), json.dumps({"error": str(e)}), attempt, job_id)
            )
            conn.commit()
            asyncio.create_task(send_log_to_br18("improvement_failed", {"job_id": job_id, "skill_id": skill_id, "error": str(e)}))

# --- Эндпоинты ---
@app.post("/skills/{skill_id}/improve")
async def improve_skill(skill_id: str, req: ImproveRequest, background_tasks: BackgroundTasks):
    try:
        await fetch_skill(skill_id)
    except HTTPException as e:
        raise e

    job_id = f"imp_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO improvement_jobs (job_id, skill_id, status, created_at, parameters, attempts) VALUES (?, ?, ?, ?, ?, ?)",
            (job_id, skill_id, "pending", created_at, json.dumps(req.dict()), 0)
        )
        conn.commit()

    asyncio.create_task(run_improvement(job_id, skill_id, req.goals or [], req.num_variants))
    background_tasks.add_task(send_log_to_br18, "improvement_started", {"job_id": job_id, "skill_id": skill_id, "goals": req.goals, "num_variants": req.num_variants})

    return {"job_id": job_id, "status": "started"}

@app.get("/improvement_jobs/{job_id}")
async def get_job_status(job_id: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT job_id, skill_id, status, created_at, completed_at, result, attempts FROM improvement_jobs WHERE job_id = ?",
            (job_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        return {
            "job_id": row[0],
            "skill_id": row[1],
            "status": row[2],
            "created_at": row[3],
            "completed_at": row[4],
            "result": json.loads(row[5]) if row[5] else None,
            "attempts": row[6]
        }

@app.post("/improvement_jobs/{job_id}/cancel")
async def cancel_improvement(job_id: str, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM improvement_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        if row[0] in ('completed', 'failed', 'cancelled'):
            raise HTTPException(status_code=400, detail=f"Job already {row[0]}")
        cur.execute("UPDATE improvement_jobs SET status = 'cancelled', completed_at = ? WHERE job_id = ?",
                    (datetime.now(timezone.utc).isoformat(), job_id))
        conn.commit()
    background_tasks.add_task(send_log_to_br18, "improvement_cancelled", {"job_id": job_id})
    return {"job_id": job_id, "status": "cancelled"}

@app.get("/improvement_proposals")
async def list_proposals(limit: int = 10, offset: int = 0, skill_id: Optional[str] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        if skill_id:
            cur.execute(
                "SELECT id, job_id, skill_id, original_skill, improved_skill, version, created_at, approved_at "
                "FROM improvement_proposals WHERE skill_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (skill_id, limit, offset)
            )
        else:
            cur.execute(
                "SELECT id, job_id, skill_id, original_skill, improved_skill, version, created_at, approved_at "
                "FROM improvement_proposals ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = cur.fetchall()
        return {
            "proposals": [
                {
                    "id": r[0],
                    "job_id": r[1],
                    "skill_id": r[2],
                    "original_skill": json.loads(r[3]) if r[3] else None,
                    "improved_skill": r[4],
                    "version": r[5],
                    "created_at": r[6],
                    "approved_at": r[7]
                }
                for r in rows
            ]
        }

@app.post("/improvement_proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: str, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT skill_id, improved_skill, version FROM improvement_proposals WHERE id = ? AND approved_at IS NULL", (proposal_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Proposal not found or already approved")
        skill_id, improved_skill, new_version = row

        try:
            current_skill = await fetch_skill(skill_id)
        except HTTPException:
            raise HTTPException(status_code=503, detail="Skill registry unavailable")

        updated_skill = current_skill.copy()
        updated_skill["prompt"] = improved_skill
        updated_skill["version"] = new_version

        success = await update_skill_in_registry(skill_id, updated_skill)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update skill in registry")

        cur.execute(
            "UPDATE improvement_proposals SET approved_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), proposal_id)
        )
        conn.commit()
    background_tasks.add_task(send_log_to_br18, "proposal_approved", {"proposal_id": proposal_id, "skill_id": skill_id, "new_version": new_version})
    return {"status": "approved", "proposal_id": proposal_id, "skill_id": skill_id, "new_version": new_version}