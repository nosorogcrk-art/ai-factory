#!/usr/bin/env python3
"""
Главный модуль C0.2 Reality Observer.
FastAPI приложение для управления сканированием и карантином.
"""

import asyncio
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from scanner import fast_scan, deep_scan, generate_reality_snapshot
from quarantine import (
    clean_old_quarantine_files,
    list_quarantine_files,
    send_message_to_argus,
    move_to_quarantine
)

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("01_ЦЕХ/01_ЖУРНАЛЫ/reality_observer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаём приложение FastAPI
app = FastAPI(
    title="C0.2 Reality Observer",
    description="Система контроля чистоты файловой системы завода",
    version="1.0.0"
)

# Глобальные переменные для состояния
scan_in_progress = False
last_scan_time = None
scan_results = {}

# Модели Pydantic
class ScanRequest(BaseModel):
    type: str = "deep"  # "fast" или "deep"
    quarantine: bool = True

class CleanRequest(BaseModel):
    days: int = 7

# Фоновые задачи
async def periodic_deep_scan():
    """Периодическое глубокое сканирование раз в час."""
    while True:
        try:
            logger.info("Запуск периодического deep_scan...")
            missing, unregistered = deep_scan()
            
            if unregistered:
                logger.warning(f"Обнаружено {len(unregistered)} незарегистрированных файлов")
                # Здесь можно добавить автоматический карантин
                # или просто логировать
            
            # Обновляем время последнего сканирования
            global last_scan_time
            last_scan_time = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Ошибка в периодическом сканировании: {e}")
        
        # Ждём 1 час
        await asyncio.sleep(3600)

async def periodic_quarantine_cleanup():
    """Периодическая очистка карантина раз в сутки."""
    while True:
        try:
            logger.info("Запуск периодической очистки карантина...")
            deleted = clean_old_quarantine_files(days=7)
            
            if deleted:
                logger.info(f"Удалено {len(deleted)} старых файлов из карантина")
            
        except Exception as e:
            logger.error(f"Ошибка при очистке карантина: {e}")
        
        # Ждём 24 часа
        await asyncio.sleep(86400)

def start_background_tasks():
    """Запускает фоновые задачи."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем задачи
    loop.create_task(periodic_deep_scan())
    loop.create_task(periodic_quarantine_cleanup())
    
    # Запускаем цикл событий в отдельном потоке
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    
    logger.info("Фоновые задачи запущены")

# Эндпоинты
@app.get("/")
async def root():
    """Корневой эндпоинт."""
    return {
        "service": "C0.2 Reality Observer",
        "version": "1.0.0",
        "status": "running",
        "last_scan": last_scan_time,
        "endpoints": [
            "/health",
            "/scan",
            "/quarantine/list",
            "/quarantine/clean",
            "/snapshot"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check эндпоинт."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "C0.2 Reality Observer"
    }

@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """
    Запускает сканирование файловой системы.
    
    Параметры:
    - type: "fast" или "deep" (по умолчанию "deep")
    - quarantine: автоматически помещать незарегистрированные файлы в карантин
    """
    global scan_in_progress
    
    if scan_in_progress:
        raise HTTPException(status_code=409, detail="Сканирование уже выполняется")
    
    scan_in_progress = True
    
    try:
        logger.info(f"Запуск сканирования типа: {request.type}")
        
        if request.type == "fast":
            missing, unregistered = fast_scan()
        elif request.type == "deep":
            missing, unregistered = deep_scan()
        else:
            raise HTTPException(status_code=400, detail="Неверный тип сканирования. Используйте 'fast' или 'deep'")
        
        # Обновляем глобальные переменные
        global last_scan_time, scan_results
        last_scan_time = datetime.now().isoformat()
        
        # Если включен карантин, перемещаем незарегистрированные файлы
        quarantined_files = []
        logger.info(f"Параметры запроса: quarantine={request.quarantine}, unregistered_count={len(unregistered)}")
        if request.quarantine and unregistered:
            logger.info(f"Автоматический карантин для {len(unregistered)} файлов")
            for file_path in unregistered:
                try:
                    logger.info(f"Попытка переместить файл в карантин: {file_path}")
                    quarantined_path = move_to_quarantine(file_path, reason="unregistered")
                    if quarantined_path:
                        logger.info(f"Файл перемещён в карантин: {quarantined_path}")
                        quarantined_files.append(str(quarantined_path))
                    else:
                        logger.warning(f"move_to_quarantine вернул None для файла: {file_path}")
                except Exception as e:
                    logger.error(f"Ошибка при перемещении файла {file_path} в карантин: {e}")
        else:
            logger.info(f"Карантин не активирован: quarantine={request.quarantine}, unregistered={bool(unregistered)}")
        
        scan_results = {
            "type": request.type,
            "timestamp": last_scan_time,
            "missing_files": [str(p) for p in missing],
            "unregistered_files": [str(p) for p in unregistered],
            "missing_count": len(missing),
            "unregistered_count": len(unregistered),
            "quarantined_files": quarantined_files,
            "quarantined_count": len(quarantined_files)
        }
        
        # Отправляем уведомление в BR18
        send_message_to_argus(
            f"Сканирование {request.type} завершено. "
            f"Отсутствует: {len(missing)}, Незарегистрировано: {len(unregistered)}, "
            f"Помещено в карантин: {len(quarantined_files)}",
            level="info",
            metadata=scan_results
        )
        
        return {
            "status": "completed",
            "scan_type": request.type,
            "timestamp": last_scan_time,
            "results": scan_results
        }
        
    except Exception as e:
        logger.error(f"Ошибка при сканировании: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        scan_in_progress = False

@app.get("/quarantine/list")
async def get_quarantine_list():
    """Возвращает список файлов в карантине."""
    try:
        files = list_quarantine_files()
        return {
            "count": len(files),
            "files": files,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Ошибка при получении списка карантина: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/quarantine/clean")
async def clean_quarantine(request: CleanRequest):
    """
    Удаляет файлы из карантина старше указанного количества дней.
    
    Параметры:
    - days: количество дней (по умолчанию 7)
    """
    try:
        logger.info(f"Запуск очистки карантина для файлов старше {request.days} дней")
        
        deleted = clean_old_quarantine_files(days=request.days)
        
        return {
            "status": "completed",
            "deleted_count": len(deleted),
            "deleted_files": [str(p) for p in deleted],
            "days_threshold": request.days,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Ошибка при очистке карантина: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/snapshot")
async def get_reality_snapshot():
    """Генерирует и возвращает снимок реальности системы."""
    try:
        snapshot = generate_reality_snapshot()
        return JSONResponse(content=snapshot)
    except Exception as e:
        logger.error(f"Ошибка при генерации снимка: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
async def get_status():
    """Возвращает текущий статус сервиса."""
    return {
        "scan_in_progress": scan_in_progress,
        "last_scan_time": last_scan_time,
        "scan_results": scan_results,
        "background_tasks": {
            "periodic_deep_scan": "running",
            "periodic_quarantine_cleanup": "running"
        },
        "timestamp": datetime.now().isoformat()
    }

# События жизненного цикла
@app.on_event("startup")
async def startup_event():
    """Действия при запуске приложения."""
    logger.info("Запуск C0.2 Reality Observer...")
    
    # Запускаем фоновые задачи
    start_background_tasks()
    
    # Выполняем начальное глубокое сканирование
    try:
        logger.info("Выполнение начального deep_scan...")
        missing, unregistered = deep_scan()
        logger.info(f"Начальное сканирование завершено. Незарегистрировано: {len(unregistered)}")
        
        global last_scan_time
        last_scan_time = datetime.now().isoformat()
        
    except Exception as e:
        logger.error(f"Ошибка при начальном сканировании: {e}")
    
    logger.info("C0.2 Reality Observer запущен")

@app.on_event("shutdown")
async def shutdown_event():
    """Действия при остановке приложения."""
    logger.info("Остановка C0.2 Reality Observer...")

if __name__ == "__main__":
    # Запуск сервера
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8092,
        reload=False,
        log_level="info"
    )