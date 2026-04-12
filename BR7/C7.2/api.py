import json
import logging
import asyncio
import httpx
from pathlib import Path
from typing import List, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import handover
from argus_watcher import watch_projects
import services

app = FastAPI(title="Handover API")

async def background_build_trigger():
    """
    Фоновая задача: раз в 5 секунд проверяет очередь патчей и запускает сборку.
    Отслеживает изменения файла по времени модификации.
    """
    last_mtime = 0
    queue_path = Path("01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json")
    while True:
        await asyncio.sleep(5)
        if not queue_path.exists():
            continue
        mtime = queue_path.stat().st_mtime
        if mtime > last_mtime:
            last_mtime = mtime
            try:
                with open(queue_path, "r") as f:
                    data = json.load(f)
                if data.get("queue"):
                    logging.info("Queue changed, triggering build")
                    # Используем check_and_build_queue, который включает вызов Packager
                    await check_and_build_queue()
            except Exception as e:
                logging.error(f"Failed to process queue: {e}")

async def run_code_audit(files: List[Dict]) -> Dict[str, Any]:
    """Отправляет код в C6.2 /audit и возвращает результат."""
    # Объединяем содержимое всех файлов в одну строку (можно и по отдельности, но для простоты – один запрос)
    code = "\n".join([f"# {f['path']}\n{f['content']}" for f in files])
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post("http://semantic-auditor:8092/audit", json={"code": code})
        resp.raise_for_status()
        return resp.json()

async def package_build_result(files: List[Dict], project_id: str = "handover_queue") -> Dict[str, Any]:
    """Вызывает C10.3 /package для упаковки кода."""
    try:
        archive_path = await services.call_packager(project_id, files)
        return {"status": "ok", "archive_path": archive_path}
    except Exception as e:
        logging.error(f"Packaging failed: {e}")
        return {"status": "error", "error": str(e)}

async def create_rework_task(project_id: str, issues: List[str], suggestions: List[str]):
    """Создаёт задачу на доработку в handover."""
    # Используем существующий эндпоинт C7.2 для создания задач (например, POST /tasks)
    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {
            "title": f"Code review failed for project {project_id}",
            "description": f"Issues: {', '.join(issues)}\nSuggestions: {', '.join(suggestions)}",
            "assigned_role": "HEPHESTUS",
            "priority": "high"
        }
        await client.post("http://handover:8080/tasks", json=payload)

async def check_and_build_queue():
    """
    Однократная проверка очереди патчей.
    Возвращает результат операции.
    """
    queue_file = Path("01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json")
    try:
        if queue_file.exists():
            with open(queue_file, "r") as f:
                queue_data = json.load(f)
            patch_ids = queue_data.get("queue", [])
            if not patch_ids:
                logging.info("Queue is empty, skipping")
                return {"status": "skipped", "message": "Queue empty", "audit_processed": False}
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                task_id = "handover_queue"
                if patch_ids:
                    task_id = patch_ids[0]  # используем первый патч как task_id
                payload = {
                    "task_id": task_id,
                    "patch_ids": patch_ids,
                    "check_skills": True,
                    "run_tests": False
                }
                logging.info(f"Calling integrator at http://integrator:8096/build with payload: {payload}")
                resp = await client.post(
                    "http://integrator:8096/build",
                    json=payload
                )
                resp.raise_for_status()
                result = resp.json()
                logging.info(f"Integrator response status: {resp.status_code}")
                logging.info(f"Integrator response body keys: {list(result.keys())}")
                
                # Получаем файлы из ответа интегратора
                files = result.get("files", [])
                logging.info(f"Extracted {len(files)} files from integrator response")
                if files:
                    logging.info(f"File names: {[f.get('filename', f.get('path', 'unknown')) for f in files[:5]]}{'...' if len(files) > 5 else ''}")
                if not files:
                    logging.warning("Integrator returned no files")
                    return {"status": "error", "message": "No files generated", "audit_processed": False}
                
                # Извлекаем project_id из queue_data (первый патч или дефолтный)
                project_id = "handover_queue"
                if queue_data.get("queue") and len(queue_data["queue"]) > 0:
                    project_id = queue_data["queue"][0]
                
                # Вызываем Packager для упаковки файлов
                package_result = await package_build_result(files, project_id)
                logging.info(f"Packaging successful: {package_result}")
                
                return {"status": "success", "message": "Build triggered and packaged", "audit_processed": True, "archive_path": package_result.get("archive_path")}
        else:
            return {"status": "skipped", "message": "No queue file", "audit_processed": False}
    except Exception as e:
        logging.error(f"Check and build queue error: {e}")
        return {"status": "error", "message": str(e), "audit_processed": False}

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(watch_projects())
    asyncio.create_task(background_build_trigger())

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/handover_api.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TakeRequest(BaseModel):
    task_id: str
    actor: str = "ГЕФЕСТ"
    comment: str = ""

class CompleteRequest(BaseModel):
    task_id: str
    actor: str = "ГЕФЕСТ"
    comment: str = ""

class DelegateRequest(BaseModel):
    task_id: str
    target: str
    actor: str = "ГЕФЕСТ"
    comment: str = ""

class BlockRequest(BaseModel):
    task_id: str
    actor: str = "АРГУС"
    comment: str = ""

class UnblockRequest(BaseModel):
    task_id: str
    actor: str = "АРГУС"
    comment: str = ""

def init_task_registry():
    try:
        if not handover.MODEL_PATH.exists():
            handover.MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(handover.MODEL_PATH, "w") as f:
                json.dump(handover.TASK_MODEL, f, indent=2)
            logging.info("Created task_model.json")
        if not handover.REGISTRY_PATH.exists():
            handover.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(handover.REGISTRY_PATH, "w") as f:
                json.dump([], f, indent=2)
            logging.info("Created empty task_registry.json")
    except Exception as e:
        logging.error(f"Failed to initialize task registry: {e}")
        raise

init_task_registry()

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/tasks")
async def list_tasks():
    try:
        with open(handover.REGISTRY_PATH, "r") as f:
            tasks = json.load(f)
        return tasks
    except Exception as e:
        logging.error(f"Failed to read task registry: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/take")
async def take(req: TakeRequest, background_tasks: BackgroundTasks):
    result = handover.handle_command({
        "command": "take",
        "task_id": req.task_id,
        "actor": req.actor,
        "comment": req.comment
    })
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    if "log_data" in result:
        background_tasks.add_task(handover._send_log_to_br18, result["log_data"]["event_type"], result["log_data"]["details"])
    return result

@app.post("/complete")
async def complete(req: CompleteRequest, background_tasks: BackgroundTasks):
    result = handover.handle_command({
        "command": "complete",
        "task_id": req.task_id,
        "actor": req.actor,
        "comment": req.comment
    })
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    if "log_data" in result:
        background_tasks.add_task(handover._send_log_to_br18, result["log_data"]["event_type"], result["log_data"]["details"])
    return result

@app.post("/delegate")
async def delegate(req: DelegateRequest, background_tasks: BackgroundTasks):
    result = handover.handle_command({
        "command": "delegate",
        "task_id": req.task_id,
        "actor": req.actor,
        "target": req.target,
        "comment": req.comment
    })
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    if "log_data" in result:
        background_tasks.add_task(handover._send_log_to_br18, result["log_data"]["event_type"], result["log_data"]["details"])
    return result

@app.post("/block")
async def block(req: BlockRequest, background_tasks: BackgroundTasks):
    result = handover.handle_command({
        "command": "block",
        "task_id": req.task_id,
        "actor": req.actor,
        "comment": req.comment
    })
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    if "log_data" in result:
        background_tasks.add_task(handover._send_log_to_br18, result["log_data"]["event_type"], result["log_data"]["details"])
    return result

@app.post("/unblock")
async def unblock(req: UnblockRequest, background_tasks: BackgroundTasks):
    result = handover.handle_command({
        "command": "unblock",
        "task_id": req.task_id,
        "actor": req.actor,
        "comment": req.comment
    })
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    if "log_data" in result:
        background_tasks.add_task(handover._send_log_to_br18, result["log_data"]["event_type"], result["log_data"]["details"])
    return result

@app.post("/trigger_build")
async def trigger_build():
    """
    Ручной триггер для проверки очереди патчей и запуска сборки.
    """
    result = await check_and_build_queue()
    return result
