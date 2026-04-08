import os
import logging
import httpx
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
import models
import services

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/integrator.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Integrator", version="0.3.0")

BR18_URL = os.environ.get("BR18_URL", "http://log-aggregator:8093/api/logs")

async def log_to_br18(level: str, message: str, component: str = "C10.1"):
    """Асинхронная отправка логов в BR18"""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            log_data = {
                "level": level,
                "message": message,
                "component": component,
                "timestamp": None  # сервер добавит свой
            }
            await client.post(BR18_URL, json=log_data)
    except Exception as e:
        logger.warning(f"Failed to send log to BR18: {e}")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/build", response_model=models.BuildResponse)
async def build(req: models.BuildRequest, background_tasks: BackgroundTasks):
    logger.info(f"Build request for task {req.task_id}, patches: {req.patch_ids}")
    # Логируем в BR18
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Build request for task {req.task_id}, patches: {req.patch_ids}")
    success, message = services.build_patches(req.task_id, req.patch_ids, req.check_skills, req.run_tests)
    if not success:
        background_tasks.add_task(log_to_br18, "ERROR", 
                                  f"Build failed for task {req.task_id}: {message}")
        raise HTTPException(status_code=500, detail=message)
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Build started for task {req.task_id}")
    return models.BuildResponse(status="started", message=message)


@app.post("/generate", response_model=models.GenerateResponse)
async def generate(req: models.GenerateRequest, background_tasks: BackgroundTasks):
    """Эндпоинт для генерации кода по спецификации L5 (заглушка)"""
    logger.info(f"Generate request for spec: {req.spec_path}")
    
    # Логируем в BR18
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Generate request for spec: {req.spec_path}")
    
    # Проверяем существование спецификации
    spec_path = Path(req.spec_path)
    spec_exists = spec_path.exists()
    
    if not spec_exists and not req.spec_content:
        error_msg = f"Specification not found at {req.spec_path} and no content provided"
        logger.error(error_msg)
        background_tasks.add_task(log_to_br18, "ERROR", error_msg)
        raise HTTPException(status_code=404, detail=error_msg)
    
    # Заглушка: пока не реализована реальная генерация кода
    message = "Code generation not yet implemented (stub)"
    logger.info(message)
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Code generation stub executed for {req.spec_path}")
    
    return models.GenerateResponse(
        status="generated",
        message=message,
        files=[]
    )
