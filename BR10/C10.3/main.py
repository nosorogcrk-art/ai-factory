"""FastAPI приложение Packager."""
import os
import time
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
import httpx
import models
import services

app = FastAPI(title="Packager", version="1.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/packager.log")
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
        "service": "C10.3",
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
    # Никакой особой инициализации не требуется
    pass


@app.get("/health")
def health():
    """Проверка работоспособности."""
    return {"status": "ok"}


@app.post("/package", response_model=models.PackageResponse)
async def package(req: models.PackageRequest, background_tasks: BackgroundTasks):
    """
    Запускает упаковку продукта.

    Args:
        req: Запрос с параметрами упаковки (repo_path, version, skills).
        background_tasks: Фоновые задачи FastAPI.

    Returns:
        Ответ с путём к архиву.
    """
    logger.info(f"Packaging request: version={req.version}, skills={req.skills}")
    await send_log_to_br18("package_started", {"repo_path": req.repo_path, "version": req.version})
    success, result = services.package(Path(req.repo_path), req.version, req.skills)
    if not success:
        await send_log_to_br18("package_failed", {"error": result})
        raise HTTPException(status_code=500, detail=result)
    await send_log_to_br18("package_completed", {"archive": result})
    return models.PackageResponse(status="ok", archive=result)