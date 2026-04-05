"""FastAPI приложение Test Stand."""
import os
import time
import asyncio
import uuid
import logging
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
import models
import services
import repositories

app = FastAPI(title="Test Stand", version="2.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/test_stand.log")
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
        "service": "C10.2",
        "event_type": event_type,
        "details": details
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(os.getenv("BR18_URL", "http://br18:8080/api/logs"), json=log_entry, timeout=2.0)
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


@app.on_event("startup")
async def startup():
    """Инициализация при старте."""
    services.check_docker_socket()
    repositories.init_db()
    repositories.delete_old_jobs()


@app.get("/health")
def health():
    """Проверка работоспособности."""
    return {"status": "ok"}


@app.post("/run")
async def run_tests(request: models.TestRequest, background_tasks: BackgroundTasks):
    """
    Запускает тесты продукта.

    Args:
        request: Параметры запуска (путь к продукту, тесты, образ, таймаут).
        background_tasks: Фоновые задачи FastAPI.

    Returns:
        Идентификатор задания и статус.
    """
    job_id = str(uuid.uuid4())[:8]
    job = {
        "job_id": job_id,
        "product_path": request.product_path,
        "test_suite": request.test_suite,
        "image": request.image,
        "timeout_seconds": request.timeout_seconds,
        "status": "pending",
        "started_at": None,
        "finished_at": None,
        "report_file": None,
        "error": None
    }
    repositories.save_job(job)
    background_tasks.add_task(services.run_tests_async, job_id, request)
    return {"job_id": job_id, "status": "pending"}


@app.get("/results/{job_id}")
def get_results(job_id: str):
    """
    Возвращает результаты выполнения задания.

    Args:
        job_id: Идентификатор задания.

    Returns:
        Данные задания.
    """
    job = repositories.load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.delete("/run/{job_id}")
async def cancel_job(job_id: str, background_tasks: BackgroundTasks):
    """
    Отменяет выполняющееся задание.

    Args:
        job_id: Идентификатор задания.
        background_tasks: Фоновые задачи FastAPI.

    Returns:
        Статус отмены.
    """
    proc = services._running_processes.pop(job_id, None)
    if not proc:
        raise HTTPException(status_code=404, detail="Job not running or already finished")
    try:
        proc.kill()
    except Exception as e:
        logger.error(f"Failed to kill process for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel job")
    job = repositories.load_job(job_id)
    if job:
        job["status"] = "cancelled"
        job["finished_at"] = datetime.now().isoformat()
        repositories.save_job(job)
        background_tasks.add_task(services.send_to_br18, "test_cancelled", {"job_id": job_id})
    return {"status": "cancelled", "job_id": job_id}