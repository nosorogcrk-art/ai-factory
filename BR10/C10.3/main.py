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


@app.post("/package")
async def package(request: dict, background_tasks: BackgroundTasks):
    """
    Упаковывает код в zip-архив.
    Поддерживает три формата запросов:
    1. Новый формат ТЗ: {"project_id": "...", "files": [{"filename": "...", "content": "..."}]}
    2. Промежуточный формат: {"files": [{"path": "...", "content": "..."}], "source_dir": "..."}
    3. Старый формат: {"repo_path": "...", "version": "...", "skills": [...]}
    """
    logger.info(f"Package request: keys={list(request.keys())}")
    
    # Если запрос пустой или не содержит обязательных полей
    if not request:
        raise HTTPException(status_code=400, detail="Empty request")
    
    # Определяем тип запроса
    if "project_id" in request and "files" in request:
        # Новый формат ТЗ
        try:
            # Проверяем, есть ли поле filename в первом файле (новый формат)
            if not request["files"]:
                raise HTTPException(status_code=400, detail="No files provided")
            
            # Проверяем формат файлов
            if "filename" in request["files"][0]:
                # Это новый формат ТЗ
                req = models.PackageRequest(**request)
                logger.info(f"Package request (new TZ format): project_id={req.project_id}, files_count={len(req.files)}")
                await send_log_to_br18("package_new_started", {"project_id": req.project_id, "files_count": len(req.files)})
                
                # Преобразуем Pydantic модели в словари для совместимости с services.create_archive
                files_list = [{"filename": f.filename, "content": f.content} for f in req.files]
                archive_path = await services.create_archive(req.project_id, files_list)
                
                # Создаем download_url (опционально)
                archive_name = archive_path.split('/')[-1]
                download_url = f"/api/download/{archive_name}"
                
                response = models.PackageResponse(
                    status="ok",
                    archive_path=archive_path,
                    download_url=download_url
                )
                
                await send_log_to_br18("package_new_completed", {"archive_path": archive_path})
                return response
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"New TZ format packaging failed: {e}")
            await send_log_to_br18("package_new_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    
    if "files" in request or "source_dir" in request:
        # Промежуточный формат запроса
        await send_log_to_br18("package_code_started", {"has_files": "files" in request, "source_dir": request.get("source_dir")})
        try:
            files_list = None
            if "files" in request:
                files_list = [{"path": f["path"], "content": f["content"]} for f in request["files"]]
            result = await services.package_code(files=files_list, source_dir=request.get("source_dir"))
            await send_log_to_br18("package_code_completed", {"artifact_url": result["artifact_url"], "version": result["version"]})
            return result
        except Exception as e:
            logger.error(f"Package code failed: {e}")
            await send_log_to_br18("package_code_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=str(e))
    else:
        # Старый формат запроса
        try:
            req = models.LegacyPackageRequest(**request)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid request format: {e}")
        
        logger.info(f"Packaging request (old format): version={req.version}, skills={req.skills}")
        await send_log_to_br18("package_started", {"repo_path": req.repo_path, "version": req.version})
        success, result = services.package(Path(req.repo_path), req.version, req.skills)
        if not success:
            await send_log_to_br18("package_failed", {"error": result})
            raise HTTPException(status_code=500, detail=result)
        await send_log_to_br18("package_completed", {"archive": result})
        return {"status": "ok", "archive": result}


@app.post("/package_code", response_model=models.PackageCodeResponse)
async def package_code_endpoint(req: models.PackageCodeRequest, background_tasks: BackgroundTasks):
    """
    Упаковывает код в zip-архив.
    
    Args:
        req: Запрос с файлами или source_dir для упаковки.
        background_tasks: Фоновые задачи FastAPI.
        
    Returns:
        Ответ с URL артефакта и версией.
    """
    logger.info(f"Package code request: files={req.files is not None}, source_dir={req.source_dir}")
    await send_log_to_br18("package_code_started", {"has_files": req.files is not None, "source_dir": req.source_dir})
    try:
        files_list = None
        if req.files:
            files_list = [{"path": f.path, "content": f.content} for f in req.files]
        result = await services.package_code(files=files_list, source_dir=req.source_dir)
        await send_log_to_br18("package_code_completed", {"artifact_url": result["artifact_url"], "version": result["version"]})
        return models.PackageCodeResponse(**result)
    except Exception as e:
        logger.error(f"Package code failed: {e}")
        await send_log_to_br18("package_code_failed", {"error": str(e)})
        raise HTTPException(status_code=500, detail=str(e))
