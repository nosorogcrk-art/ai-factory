import httpx
import logging
import time
from typing import List

logger = logging.getLogger(__name__)
PACKAGER_URL = "http://packager:8082/package"  # внутренний порт

async def call_packager(project_id: str, files: list) -> str:
    """
    Отправляет запрос к Packager для создания ZIP-архива.
    Возвращает путь к архиву (строка).
    При ошибке выбрасывает исключение.
    Поддерживает два формата файлов:
    1. {"filename": "...", "content": "..."}
    2. {"path": "...", "content": "..."} (преобразуется в filename = basename(path))
    """
    processed_files = []
    for f in files:
        if "filename" in f:
            processed_files.append({"filename": f["filename"], "content": f["content"]})
        elif "path" in f:
            # Извлекаем имя файла из пути
            import os
            filename = os.path.basename(f["path"])
            processed_files.append({"filename": filename, "content": f["content"]})
        else:
            raise ValueError(f"File entry must have either 'filename' or 'path' key: {f}")
    
    payload = {
        "project_id": project_id,
        "files": processed_files
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(PACKAGER_URL, json=payload)
        resp.raise_for_status()
        data = resp.json()  # httpx.Response.json() - синхронный метод, не требует await
        logger.info(f"Packager created archive: {data['archive_path']}")
        return data["archive_path"]

async def trigger_build_from_queue(patch_ids: List[str]):
    """Вызывает интегратор C10.1 для генерации кода по списку патчей."""
    logger.info(f"Triggering build for {len(patch_ids)} patch IDs: {patch_ids[:5]}{'...' if len(patch_ids) > 5 else ''}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "task_id": f"auto_{int(time.time())}",
            "patch_ids": patch_ids
        }
        logger.info(f"Sending request to integrator: {payload}")
        try:
            resp = await client.post("http://integrator:8096/build", json=payload)
            resp.raise_for_status()
            result = resp.json()  # httpx.Response.json() - синхронный метод, не требует await
            logger.info(f"Integrator response status: {resp.status_code}")
            logger.info(f"Integrator response body: {result}")
            files = result.get("files", [])
            logger.info(f"Extracted {len(files)} files: {[f.get('filename') for f in files]}")
            logger.info(f"Build triggered, got {len(files)} files")
            return result
        except Exception as e:
            logger.error(f"Failed to trigger build: {e}")
            raise
