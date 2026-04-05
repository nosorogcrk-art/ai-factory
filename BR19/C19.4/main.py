import os
import json
import logging
import sqlite3
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
import httpx

# --- Конфигурация ---
DB_PATH = Path(os.getenv("DB_PATH", "/data/ab_tester.db"))
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/ab_tester.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(LOG_FILE, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# --- Переменные окружения ---
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))

# --- SQLite инициализация ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS experiments (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL,
            variants TEXT NOT NULL,
            weights TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            started_at TEXT,
            ended_at TEXT
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS experiment_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            experiment_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            variant TEXT NOT NULL,
            assigned_at TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments (id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_experiment_user ON experiment_assignments (experiment_id, user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_assigned_at ON experiment_assignments (assigned_at)')
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_PATH)

# --- Отправка логов в BR18 ---
async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    async def _send():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    BR18_URL,
                    json={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": "C19.4",
                        "event_type": event_type,
                        "details": details
                    },
                    timeout=5.0
                )
                logger.info(f"Log sent to BR18: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")
    background_tasks.add_task(_send)

# --- Модели Pydantic с валидацией ---
class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    variants: List[str] = Field(..., min_length=2)
    weights: Optional[List[float]] = None

    @validator('variants')
    def unique_variants(cls, v):
        if len(v) != len(set(v)):
            raise ValueError('Variants must be unique')
        return v

    @validator('weights')
    def validate_weights(cls, v, values):
        if v is not None:
            if len(v) != len(values.get('variants', [])):
                raise ValueError('Number of weights must match number of variants')
            if not all(w > 0 for w in v):
                raise ValueError('All weights must be positive')
        return v

class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    variants: Optional[List[str]] = None
    weights: Optional[List[float]] = None

    @validator('variants')
    def unique_variants(cls, v):
        if v is not None and len(v) != len(set(v)):
            raise ValueError('Variants must be unique')
        return v

    @validator('weights')
    def validate_weights(cls, v, values):
        if v is not None:
            variants = values.get('variants')
            if variants is not None and len(v) != len(variants):
                raise ValueError('Number of weights must match number of variants')
            if not all(w > 0 for w in v):
                raise ValueError('All weights must be positive')
        return v

# --- FastAPI ---
app = FastAPI(title="A/B Tester", version="0.3.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- CRUD экспериментов ---
@app.post("/experiments")
async def create_experiment(exp: ExperimentCreate, background_tasks: BackgroundTasks):
    exp_id = f"exp_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    variants_json = json.dumps(exp.variants)
    weights_json = json.dumps(exp.weights) if exp.weights else None
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO experiments (id, name, description, status, variants, weights, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (exp_id, exp.name, exp.description, "draft", variants_json, weights_json, now, now)
        )
        conn.commit()
    await send_log_to_br18("experiment_created", {"experiment_id": exp_id, "name": exp.name}, background_tasks)
    return {"id": exp_id, "status": "created"}

@app.get("/experiments")
async def list_experiments(limit: int = 20, offset: int = 0):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM experiments "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        rows = cur.fetchall()
        return {
            "experiments": [
                {
                    "id": r[0],
                    "name": r[1],
                    "description": r[2],
                    "status": r[3],
                    "created_at": r[4],
                    "updated_at": r[5]
                }
                for r in rows
            ]
        }

@app.get("/experiments/{exp_id}")
async def get_experiment(exp_id: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, status, variants, weights, created_at, updated_at, started_at, ended_at "
                    "FROM experiments WHERE id = ?", (exp_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Experiment not found")
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "status": row[3],
            "variants": json.loads(row[4]),
            "weights": json.loads(row[5]) if row[5] else None,
            "created_at": row[6],
            "updated_at": row[7],
            "started_at": row[8],
            "ended_at": row[9]
        }

@app.patch("/experiments/{exp_id}")
async def update_experiment(exp_id: str, update: ExperimentUpdate, background_tasks: BackgroundTasks):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM experiments WHERE id = ?", (exp_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Experiment not found")
        current_status = row[0]

        if current_status == "active" and (update.variants is not None or update.weights is not None):
            raise HTTPException(status_code=400, detail="Cannot change variants or weights while experiment is active")

        updates = []
        params = []
        old_status = current_status
        if update.name is not None:
            updates.append("name = ?")
            params.append(update.name)
        if update.description is not None:
            updates.append("description = ?")
            params.append(update.description)
        if update.status is not None:
            allowed = {
                "draft": ["active", "paused", "ended"],
                "active": ["paused", "ended"],
                "paused": ["active", "ended"],
                "ended": []
            }
            if update.status not in allowed.get(current_status, []):
                raise HTTPException(status_code=400, detail=f"Invalid status transition from {current_status} to {update.status}")
            updates.append("status = ?")
            params.append(update.status)
            if update.status == "active" and current_status != "active":
                updates.append("started_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
            if update.status == "ended":
                updates.append("ended_at = ?")
                params.append(datetime.now(timezone.utc).isoformat())
            old_status = current_status
            current_status = update.status
        if update.variants is not None:
            updates.append("variants = ?")
            params.append(json.dumps(update.variants))
        if update.weights is not None:
            updates.append("weights = ?")
            params.append(json.dumps(update.weights))
        if not updates:
            return {"message": "No changes"}
        updates.append("updated_at = ?")
        params.append(datetime.now(timezone.utc).isoformat())
        params.append(exp_id)
        query = f"UPDATE experiments SET {', '.join(updates)} WHERE id = ?"
        cur.execute(query, params)
        conn.commit()
    if update.status and update.status != old_status:
        await send_log_to_br18("experiment_status_changed", {
            "experiment_id": exp_id,
            "old_status": old_status,
            "new_status": update.status
        }, background_tasks)
    return {"message": "updated"}

@app.get("/experiments/{exp_id}/stats")
async def get_experiment_stats(exp_id: str):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name FROM experiments WHERE id = ?", (exp_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Experiment not found")
        cur.execute(
            "SELECT variant, COUNT(*) FROM experiment_assignments WHERE experiment_id = ? GROUP BY variant",
            (exp_id,)
        )
        rows = cur.fetchall()
        stats = {row[0]: row[1] for row in rows}
        cur.execute("SELECT variants FROM experiments WHERE id = ?", (exp_id,))
        variants = json.loads(cur.fetchone()[0])
        full_stats = {v: stats.get(v, 0) for v in variants}
        return {
            "experiment_id": exp_id,
            "total_assignments": sum(full_stats.values()),
            "distribution": full_stats
        }

def select_variant(variants: List[str], weights: Optional[List[float]] = None) -> str:
    if weights is None:
        return random.choice(variants)
    return random.choices(variants, weights=weights, k=1)[0]

@app.post("/experiments/{exp_id}/assign")
async def assign_variant(exp_id: str, user_id: str, background_tasks: BackgroundTasks):
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status, variants, weights FROM experiments WHERE id = ?", (exp_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Experiment not found")
        status, variants_json, weights_json = row
        if status != "active":
            raise HTTPException(status_code=400, detail="Experiment is not active")
        variants = json.loads(variants_json)
        weights = json.loads(weights_json) if weights_json else None
        cur.execute("SELECT variant FROM experiment_assignments WHERE experiment_id = ? AND user_id = ?", (exp_id, user_id))
        existing = cur.fetchone()
        if existing:
            return {"experiment_id": exp_id, "variant": existing[0], "already_assigned": True}
        variant = select_variant(variants, weights)
        now = datetime.now(timezone.utc).isoformat()
        cur.execute(
            "INSERT INTO experiment_assignments (experiment_id, user_id, variant, assigned_at) VALUES (?, ?, ?, ?)",
            (exp_id, user_id, variant, now)
        )
        conn.commit()
    await send_log_to_br18("variant_assigned", {
        "experiment_id": exp_id,
        "user_id": user_id,
        "variant": variant
    }, background_tasks)
    return {"experiment_id": exp_id, "variant": variant}