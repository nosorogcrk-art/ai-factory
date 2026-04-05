"""FastAPI приложение Project Dashboard."""
import os
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import models
import services

app = FastAPI(title="Project Dashboard")

# Переменные окружения
REGISTRY_URL = os.getenv("REGISTRY_URL", "http://registry:8000")
METRICS_URL = os.getenv("METRICS_URL", "http://metrics-dashboard:8094")
SKILL_REGISTRY_URL = os.getenv("SKILL_REGISTRY_URL", "http://skill-registry:8088")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
TASK_REGISTRY_PATH = os.getenv("TASK_REGISTRY_PATH", "01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/dashboard.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_log_to_br18(event_type: str, details: dict):
    """Отправляет лог в BR18 асинхронно."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "C4.1",
        "event_type": event_type,
        "details": details
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(BR18_URL, json=log_entry, timeout=2.0)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware для логирования всех запросов."""
    start = time.time()
    response = await call_next(request)
    duration = (time.time() - start) * 1000
    asyncio.create_task(send_log_to_br18("api_call", {
        "method": request.method,
        "path": request.url.path,
        "status_code": response.status_code,
        "response_time_ms": round(duration, 2)
    }))
    return response


@app.get("/health")
async def health():
    """Проверка работоспособности."""
    return {"status": "ok"}


@app.get("/api/status", response_model=models.MetricsResponse)
async def get_status():
    """
    Возвращает агрегированные метрики:
    - метрики из BR18
    - список веток из BR0
    - список задач из реестра
    - статистику навыков
    """
    try:
        result = await services.aggregate_status(
            REGISTRY_URL, METRICS_URL, SKILL_REGISTRY_URL, TASK_REGISTRY_PATH
        )
        asyncio.create_task(send_log_to_br18("status_fetched", {"status": "ok"}))
        return result
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        asyncio.create_task(send_log_to_br18("status_error", {"error": str(e)}))
        return models.MetricsResponse(
            metrics={},
            branches=[],
            tasks=[],
            skill_stats={"total": 0, "active": 0},
            last_update=datetime.now().isoformat()
        )


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    """Главная страница дашборда."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())