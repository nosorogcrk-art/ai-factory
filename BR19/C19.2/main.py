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
DB_PATH = Path(os.getenv("DB_PATH", "/data/prompt_optimizer.db"))
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/prompt_optimizer.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Переменные окружения ---
LOG_ANALYZER_URL = os.getenv("LOG_ANALYZER_URL", "http://log-analyzer:8101")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

# --- SQLite инициализация ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS optimization_jobs (
            job_id TEXT PRIMARY KEY,
            prompt_id TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            completed_at TEXT,
            result TEXT,
            parameters TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS candidates (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            prompt_text TEXT NOT NULL,
            version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (job_id) REFERENCES optimization_jobs (job_id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_optimization_jobs_prompt_id ON optimization_jobs (prompt_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_optimization_jobs_created_at ON optimization_jobs (created_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_candidates_job_id ON candidates (job_id)')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_PATH)

class OptimizeRequest(BaseModel):
    goals: Optional[List[str]] = None
    num_variants: int = Field(3, ge=1, le=10)

app = FastAPI(title="Prompt Optimizer", version="0.4.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

# --- Отправка логов в BR18 ---
async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    async def _send():
        try:
            async with httpx.AsyncClient() as http_client:
                await http_client.post(
                    BR18_URL,
                    json={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": "C19.2",
                        "event_type": event_type,
                        "details": details
                    },
                    timeout=5.0
                )
                logger.info(f"Log sent to BR18: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")
    background_tasks.add_task(_send)

@app.on_event("startup")
async def startup():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT job_id, prompt_id, parameters FROM optimization_jobs WHERE status = 'pending'")
        rows = cur.fetchall()
        for job_id, prompt_id, params_json in rows:
            params = json.loads(params_json) if params_json else {}
            goals = params.get("goals", [])
            num_variants = params.get("num_variants", 3)
            logger.info(f"Recovering pending job {job_id}")
            asyncio.create_task(run_optimization(job_id, prompt_id, goals, num_variants))

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Заглушки (заменятся позже) ---
async def fetch_current_prompt(prompt_id: str) -> str:
    logger.info(f"Stub: returning fake prompt for {prompt_id}")
    return f"Stub prompt for {prompt_id}"

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

async def generate_candidates(prompt_id: str, current_prompt: str, issues: dict, goals: List[str], num_variants: int) -> List[dict]:
    logger.info(f"Generating {num_variants} candidates for {prompt_id}")
    candidates = []
    seen_texts = set()
    for i in range(num_variants):
        version = f"v1.0.{i+1}"
        variant = f"[STUB] Improved version {i+1} of prompt for {prompt_id}.\n\nOriginal:\n{current_prompt[:200]}...\n\nBased on issues: {json.dumps(issues)[:100]}"
        if variant in seen_texts:
            continue
        seen_texts.add(variant)
        candidates.append({
            "id": f"cand_{uuid.uuid4().hex[:8]}",
            "prompt_text": variant,
            "version": version,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    return candidates

async def is_job_cancelled(job_id: str) -> bool:
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM optimization_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        return row and row[0] == 'cancelled'

async def run_optimization(job_id: str, prompt_id: str, goals: List[str], num_variants: int):
    logger.info(f"Optimization job {job_id} started for prompt {prompt_id}")
    with get_connection() as conn:
        cur = conn.cursor()
        try:
            if await is_job_cancelled(job_id):
                logger.info(f"Job {job_id} cancelled before execution")
                return

            current_prompt = await fetch_current_prompt(prompt_id)
            issues = await fetch_issues_from_log_analyzer()
            candidates = await generate_candidates(prompt_id, current_prompt, issues, goals, num_variants)

            for c in candidates:
                cur.execute(
                    "INSERT INTO candidates (id, job_id, prompt_text, version, created_at) VALUES (?, ?, ?, ?, ?)",
                    (c["id"], job_id, c["prompt_text"], c["version"], c["created_at"])
                )

            cur.execute(
                "UPDATE optimization_jobs SET status = 'completed', completed_at = ?, result = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(),
                 json.dumps({"candidate_ids": [c["id"] for c in candidates], "message": "Optimization completed"}),
                 job_id)
            )
            conn.commit()
            logger.info(f"Optimization job {job_id} completed, generated {len(candidates)} candidates")
            # Отправляем лог в BR18 (без background_tasks, так как задача уже в фоне)
            asyncio.create_task(send_log_to_br18("optimization_completed", {"job_id": job_id, "prompt_id": prompt_id, "candidates_count": len(candidates)}, BackgroundTasks()))
        except Exception as e:
            logger.error(f"Optimization job {job_id} failed: {e}")
            cur.execute(
                "UPDATE optimization_jobs SET status = 'failed', completed_at = ?, result = ? WHERE job_id = ?",
                (datetime.now(timezone.utc).isoformat(), json.dumps({"error": str(e)}), job_id)
            )
            conn.commit()
            asyncio.create_task(send_log_to_br18("optimization_failed", {"job_id": job_id, "prompt_id": prompt_id, "error": str(e)}, BackgroundTasks()))

@app.post("/optimize/{prompt_id}")
async def optimize(prompt_id: str, req: OptimizeRequest, background_tasks: BackgroundTasks):
    job_id = f"opt_{uuid.uuid4().hex[:8]}"
    created_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO optimization_jobs (job_id, prompt_id, status, created_at, parameters) VALUES (?, ?, ?, ?, ?)",
            (job_id, prompt_id, "pending", created_at, json.dumps(req.dict()))
        )
        conn.commit()

    asyncio.create_task(run_optimization(job_id, prompt_id, req.goals or [], req.num_variants))
    await send_log_to_br18("optimization_started", {"job_id": job_id, "prompt_id": prompt_id, "goals": req.goals, "num_variants": req.num_variants}, background_tasks)

    return {"job_id": job_id, "status": "started"}

@app.get("/optimize/{prompt_id}/status")
async def get_optimization_status(prompt_id: str, limit: int = 10, offset: int = 0):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT job_id, status, created_at, completed_at, result FROM optimization_jobs WHERE prompt_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (prompt_id, limit, offset)
        )
        rows = cur.fetchall()
        return {
            "jobs": [
                {
                    "job_id": r[0],
                    "status": r[1],
                    "created_at": r[2],
                    "completed_at": r[3],
                    "result": json.loads(r[4]) if r[4] else None
                }
                for r in rows
            ]
        }

@app.post("/optimize/{job_id}/cancel")
async def cancel_optimization(job_id: str, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM optimization_jobs WHERE job_id = ?", (job_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        if row[0] in ('completed', 'failed', 'cancelled'):
            raise HTTPException(status_code=400, detail=f"Job already {row[0]}")
        cur.execute("UPDATE optimization_jobs SET status = 'cancelled', completed_at = ? WHERE job_id = ?",
                    (datetime.now(timezone.utc).isoformat(), job_id))
        conn.commit()
    await send_log_to_br18("optimization_cancelled", {"job_id": job_id}, background_tasks)
    return {"job_id": job_id, "status": "cancelled"}

@app.get("/candidates")
async def list_candidates(limit: int = 10, offset: int = 0, job_id: Optional[str] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        if job_id:
            cur.execute(
                "SELECT id, prompt_text, version, created_at FROM candidates WHERE job_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (job_id, limit, offset)
            )
        else:
            cur.execute(
                "SELECT id, prompt_text, version, created_at FROM candidates ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
        rows = cur.fetchall()
        return {
            "candidates": [
                {"id": r[0], "prompt_text": r[1], "version": r[2], "created_at": r[3]}
                for r in rows
            ]
        }

@app.get("/jobs/{job_id}/candidates")
async def get_job_candidates(job_id: str, limit: int = 10, offset: int = 0):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT job_id FROM optimization_jobs WHERE job_id = ?", (job_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Job not found")
        cur.execute(
            "SELECT id, prompt_text, version, created_at FROM candidates WHERE job_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (job_id, limit, offset)
        )
        rows = cur.fetchall()
        return {
            "candidates": [
                {"id": r[0], "prompt_text": r[1], "version": r[2], "created_at": r[3]}
                for r in rows
            ]
        }

@app.post("/candidates/{candidate_id}/promote")
async def promote_candidate(candidate_id: str, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT prompt_text, version, job_id FROM candidates WHERE id = ?", (candidate_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        prompt_text, version, job_id = row
        logger.info(f"Promote candidate {candidate_id} (version {version}) for job {job_id}")
        await send_log_to_br18("candidate_promoted", {"candidate_id": candidate_id, "version": version, "job_id": job_id}, background_tasks)
    return {"status": "not_implemented", "candidate_id": candidate_id}