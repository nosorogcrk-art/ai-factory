import os
import logging
import httpx
import traceback
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
    
    if not req.task_id:
        raise HTTPException(status_code=400, detail="Missing 'task_id'")
    if not req.patch_ids:
        raise HTTPException(status_code=400, detail="Missing or empty 'patch_ids'")
    
    try:
        files = await services.generate_code_from_patches(req.task_id, req.patch_ids)
        logger.info(f"Generated {len(files)} files for task {req.task_id}")
        background_tasks.add_task(log_to_br18, "INFO", 
                                  f"Generated {len(files)} files for task {req.task_id}")
        return models.BuildResponse(
            status="ok", 
            message=f"Generated {len(files)} files",
            files=files
        )
    except Exception as e:
        logger.error(f"Build failed: {e}")
        logger.error(traceback.format_exc())
        background_tasks.add_task(log_to_br18, "ERROR", 
                                  f"Build failed for task {req.task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


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


@app.post("/generate-from-l5", response_model=models.GenerateFromL5Response)
async def generate_from_l5(req: models.GenerateFromL5Request, background_tasks: BackgroundTasks):
    """Генерация кода из L5 спецификации через навык code_generation"""
    logger.info(f"Generate from L5 request for container {req.container_id}")
    
    # Логируем в BR18
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Generate from L5 request for container {req.container_id}")
    
    if not req.container_id or not req.spec:
        error_msg = "Missing container_id or spec"
        logger.error(error_msg)
        background_tasks.add_task(log_to_br18, "ERROR", error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    try:
        files = await services.generate_code_from_l5(req.container_id, req.spec)
        logger.info(f"Generated {len(files)} files for container {req.container_id}")
        background_tasks.add_task(log_to_br18, "INFO", 
                                  f"Generated {len(files)} files for container {req.container_id}")
        return models.GenerateFromL5Response(
            status="success",
            files=[models.FileItem(path=f["path"], content=f["content"]) for f in files]
        )
    except Exception as e:
        error_msg = f"Failed to generate code: {str(e)}"
        logger.error(error_msg)
        background_tasks.add_task(log_to_br18, "ERROR", error_msg)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/build_from_queue")
async def build_from_queue(request: dict, background_tasks: BackgroundTasks):
    """Принимает очередь патчей и запускает сборку для каждого"""
    queue = request.get("queue")
    if queue is None:
        error_msg = "Missing 'queue' field"
        logger.error(error_msg)
        background_tasks.add_task(log_to_br18, "ERROR", error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    
    logger.info(f"Build from queue request with {len(queue)} items")
    background_tasks.add_task(log_to_br18, "INFO", 
                              f"Build from queue request with {len(queue)} items")
    
    try:
        result = await services.build_from_queue(queue)
        logger.info(f"Build from queue completed: {result['total']} items processed")
        background_tasks.add_task(log_to_br18, "INFO", 
                                  f"Build from queue completed: {result['total']} items processed")
        return {"status": "success", "result": result}
    except Exception as e:
        error_msg = f"Failed to build from queue: {str(e)}"
        logger.error(error_msg)
        background_tasks.add_task(log_to_br18, "ERROR", error_msg)
        raise HTTPException(status_code=500, detail=str(e))
