import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

# --- Конфигурация ---
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/cognitive_engine.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Исправлено: теперь значение по умолчанию соответствует имени сервиса в docker-compose
METRICS_URL = os.getenv("METRICS_URL", "http://metrics-dashboard:8094/api/metrics")
PROMPT_OPTIMIZER_URL = os.getenv("PROMPT_OPTIMIZER_URL", "http://prompt-optimizer:8102")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))

app = FastAPI(title="Cognitive Engine", version="0.1.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

# --- Получение метрик из C18.2 ---
async def fetch_metrics(metric_name: Optional[str] = None) -> dict:
    try:
        if metric_name:
            resp = await client.get(f"{METRICS_URL}/{metric_name}")
        else:
            resp = await client.get(METRICS_URL)
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        logger.error("Timeout fetching metrics")
        raise HTTPException(status_code=504, detail="Metrics service timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"Metrics service returned {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="Metrics service error")
    except Exception as e:
        logger.error(f"Failed to fetch metrics: {e}")
        raise HTTPException(status_code=503, detail=f"Could not fetch metrics: {e}")

# --- Запуск оптимизации промпта в C19.2 ---
async def optimize_prompt(prompt_id: str, goals: List[str], num_variants: int = 3) -> dict:
    try:
        resp = await client.post(
            f"{PROMPT_OPTIMIZER_URL}/optimize/{prompt_id}",
            json={"goals": goals, "num_variants": num_variants}
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        logger.error("Timeout optimizing prompt")
        raise HTTPException(status_code=504, detail="Prompt Optimizer timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"Prompt Optimizer returned {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="Prompt Optimizer error")
    except Exception as e:
        logger.error(f"Failed to optimize prompt: {e}")
        raise HTTPException(status_code=503, detail=f"Could not optimize prompt: {e}")

# --- Получение результатов оптимизации (кандидатов) ---
async def get_candidates(job_id: str) -> dict:
    try:
        resp = await client.get(f"{PROMPT_OPTIMIZER_URL}/jobs/{job_id}")
        resp.raise_for_status()
        return resp.json()
    except httpx.TimeoutException:
        logger.error("Timeout fetching candidates")
        raise HTTPException(status_code=504, detail="Prompt Optimizer timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"Prompt Optimizer returned {e.response.status_code}")
        raise HTTPException(status_code=e.response.status_code, detail="Prompt Optimizer error")
    except Exception as e:
        logger.error(f"Failed to get candidates: {e}")
        raise HTTPException(status_code=503, detail=f"Could not get candidates: {e}")

# --- API эндпоинты Cognitive Engine ---
class OptimizePromptRequest(BaseModel):
    prompt_id: str
    goals: List[str] = ["reduce_errors", "improve_clarity"]
    num_variants: int = 3

@app.post("/cognitive/optimize")
async def cognitive_optimize(req: OptimizePromptRequest):
    """Запускает оптимизацию промпта на основе метрик."""
    # 1. Получить метрики (можно для конкретной метрики, связанной с промптом)
    metrics = await fetch_metrics()
    # 2. Передать в Prompt Optimizer
    result = await optimize_prompt(req.prompt_id, req.goals, req.num_variants)
    return {"metrics": metrics, "optimization": result}

@app.get("/cognitive/metrics")
async def get_metrics(metric_name: Optional[str] = None):
    """Прокси для получения метрик из C18.2."""
    data = await fetch_metrics(metric_name)
    return data

@app.get("/cognitive/prompt/job/{job_id}")
async def get_prompt_optimization_result(job_id: str):
    """Получить результат оптимизации по job_id."""
    data = await get_candidates(job_id)
    return data