import os
import json
import logging
import sqlite3
import uuid
import random
import asyncio
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, validator
import httpx

# --- Самодельная функция z-теста пропорций (без scipy) ---
def proportions_ztest(count: List[int], nobs: List[int]):
    """
    Двухвыборочный z-тест для пропорций.
    count: список количества успехов в каждой группе [success_control, success_treatment]
    nobs:  список размеров выборок [n_control, n_treatment]
    возвращает (z_stat, p_value)
    """
    p1 = count[0] / nobs[0]
    p2 = count[1] / nobs[1]
    p_pooled = (count[0] + count[1]) / (nobs[0] + nobs[1])
    se = math.sqrt(p_pooled * (1 - p_pooled) * (1/nobs[0] + 1/nobs[1]))
    if se == 0:
        return 0.0, 1.0
    z = (p1 - p2) / se
    # двустороннее p-value
    p_value = 2 * (1 - math.erf(abs(z) / math.sqrt(2)))
    return z, p_value

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
BR20_URL = os.getenv("BR20_URL", "")

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
            ended_at TEXT,
            result TEXT,
            object_type TEXT,
            object_id TEXT
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
    conn.execute('''
        CREATE TABLE IF NOT EXISTS experiment_metrics (
            id TEXT PRIMARY KEY,
            experiment_id TEXT NOT NULL,
            variant TEXT NOT NULL,
            success INTEGER,
            duration_ms INTEGER,
            cost_usd REAL,
            context TEXT,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (experiment_id) REFERENCES experiments (id)
        )
    ''')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_experiments_status ON experiments (status)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_experiment_user ON experiment_assignments (experiment_id, user_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_assignments_assigned_at ON experiment_assignments (assigned_at)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_exp ON experiment_metrics(experiment_id)')
    conn.execute('CREATE INDEX IF NOT EXISTS idx_metrics_variant ON experiment_metrics(variant)')
    # Миграция: добавляем колонки object_type и object_id, если их нет
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(experiments)")
    columns = [col[1] for col in cur.fetchall()]
    if "object_type" not in columns:
        cur.execute("ALTER TABLE experiments ADD COLUMN object_type TEXT")
    if "object_id" not in columns:
        cur.execute("ALTER TABLE experiments ADD COLUMN object_id TEXT")
    conn.commit()
    conn.close()

init_db()

def get_connection():
    return sqlite3.connect(DB_PATH)

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

class MetricPayload(BaseModel):
    experiment_id: str
    variant: str
    success: Optional[bool] = None
    duration_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    context: Optional[str] = None

app = FastAPI(title="A/B Tester", version="1.1.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

# --- Фоновая задача анализа ---
async def analyze_experiments_background():
    while True:
        await asyncio.sleep(3600)
        try:
            with get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, variants FROM experiments WHERE status = 'running'")
                experiments = cur.fetchall()
                for exp_id, variants_json in experiments:
                    variants = json.loads(variants_json)
                    if len(variants) != 2:
                        continue
                    control, treatment = variants[0], variants[1]
                    cur.execute(
                        "SELECT success FROM experiment_metrics WHERE experiment_id = ? AND variant = ? AND success IS NOT NULL",
                        (exp_id, control)
                    )
                    control_data = [row[0] for row in cur.fetchall()]
                    cur.execute(
                        "SELECT success FROM experiment_metrics WHERE experiment_id = ? AND variant = ? AND success IS NOT NULL",
                        (exp_id, treatment)
                    )
                    treatment_data = [row[0] for row in cur.fetchall()]
                    if len(control_data) < 10 or len(treatment_data) < 10:
                        continue
                    count = [sum(control_data), sum(treatment_data)]
                    nobs = [len(control_data), len(treatment_data)]
                    _, p_value = proportions_ztest(count, nobs)
                    improvement = (sum(treatment_data)/len(treatment_data) - sum(control_data)/len(control_data)) / (sum(control_data)/len(control_data)) if sum(control_data) > 0 else 0
                    result = {
                        "p_value": p_value,
                        "improvement": improvement,
                        "control_rate": sum(control_data)/len(control_data),
                        "treatment_rate": sum(treatment_data)/len(treatment_data),
                        "control_count": len(control_data),
                        "treatment_count": len(treatment_data)
                    }
                    cur.execute(
                        "UPDATE experiments SET status = 'completed', ended_at = ?, result = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), json.dumps(result), exp_id)
                    )
                    conn.commit()
                    if p_value < 0.05 and improvement > 0 and BR20_URL:
                        await trigger_deploy(exp_id, treatment)
        except Exception as e:
            logger.error(f"Background analysis error: {e}")

async def trigger_deploy(experiment_id: str, winning_variant: str):
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BR20_URL}/deploy",
                json={
                    "experiment_id": experiment_id,
                    "winning_variant": winning_variant
                },
                timeout=10.0
            )
            if resp.status_code == 200:
                logger.info(f"Deploy triggered for experiment {experiment_id}, variant {winning_variant}")
            else:
                logger.error(f"Deploy failed: {resp.status_code} - {resp.text}")
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE experiments SET status = 'deploy_failed' WHERE id = ?",
                        (experiment_id,)
                    )
                    conn.commit()
    except Exception as e:
        logger.error(f"Deploy request error: {e}")

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(analyze_experiments_background())

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
        cur.execute("SELECT id, name, description, status, variants, weights, created_at, updated_at, started_at, ended_at, result "
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
            "ended_at": row[9],
            "result": json.loads(row[10]) if row[10] else None
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

@app.get("/experiments/completed")
async def get_completed_experiments(limit: int = 100):
    """
    Возвращает завершённые эксперименты (status='completed'), у которых
    в поле result: p_value < 0.05 и improvement > 0.
    Требует наличия полей object_type и object_id (могут быть NULL – такие не включаются).
    """
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, variants, result, object_type, object_id, completed_at "
            "FROM experiments WHERE status = 'completed' AND result IS NOT NULL "
            "AND object_type IS NOT NULL AND object_id IS NOT NULL "
            "ORDER BY completed_at DESC LIMIT ?", (limit,)
        )
        rows = cur.fetchall()
        experiments = []
        for row in rows:
            exp_id, name, variants_json, result_json, obj_type, obj_id, completed_at = row
            result = json.loads(result_json)
            if result.get("p_value", 1.0) < 0.05 and result.get("improvement", 0) > 0:
                experiments.append({
                    "id": exp_id,
                    "name": name,
                    "variants": json.loads(variants_json),
                    "result": result,
                    "object_type": obj_type,
                    "object_id": obj_id,
                    "completed_at": completed_at
                })
        return {"experiments": experiments}

# --- Новый эндпоинт для сбора метрик (P19.4.3) ---
@app.post("/api/metrics")
async def submit_metric(payload: MetricPayload, background_tasks: BackgroundTasks):
    metric_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    success_int = 1 if payload.success else (0 if payload.success is False else None)
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO experiment_metrics (id, experiment_id, variant, success, duration_ms, cost_usd, context, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (metric_id, payload.experiment_id, payload.variant, success_int, payload.duration_ms, payload.cost_usd, payload.context, now)
        )
        conn.commit()
    await send_log_to_br18("metric_submitted", {
        "experiment_id": payload.experiment_id,
        "variant": payload.variant,
        "metric_id": metric_id
    }, background_tasks)
    return {"status": "accepted", "id": metric_id}