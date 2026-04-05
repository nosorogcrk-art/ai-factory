import os
import time
import asyncio
import logging
import json
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import httpx
import models
import services

app = FastAPI(title="Command Console")

HANDOVER_URL = os.getenv("HANDOVER_URL", "http://handover:8080")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/console.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_log_to_br18(event_type: str, details: dict):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "C4.3",
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


@app.post("/api/command", response_model=models.CommandResponse)
async def execute_command(req: models.CommandRequest):
    """Принимает команду, парсит, вызывает соответствующий сервис и возвращает результат."""
    command = req.command.strip()
    if not command:
        raise HTTPException(status_code=400, detail="Empty command")

    parsed = services.parse_command(command)
    cmd = parsed["cmd"]
    args = parsed["args"]

    result = {"success": False, "output": "Unknown command"}

    if cmd == "take" and len(args) == 1:
        task_id = args[0]
        resp = await services.call_handover("POST", "/take", {"task_id": task_id, "actor": "ГЕФЕСТ"}, HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": f"Task {task_id} taken"}

    elif cmd == "complete" and len(args) == 1:
        task_id = args[0]
        resp = await services.call_handover("POST", "/complete", {"task_id": task_id, "actor": "ГЕФЕСТ"}, HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": f"Task {task_id} completed"}

    elif cmd == "delegate" and len(args) == 2:
        task_id, target = args[0], args[1]
        resp = await services.call_handover("POST", "/delegate", {"task_id": task_id, "target": target, "actor": "ГЕФЕСТ"}, HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": f"Task {task_id} delegated to {target}"}

    elif cmd == "block" and len(args) == 1:
        task_id = args[0]
        resp = await services.call_handover("POST", "/block", {"task_id": task_id, "actor": "ГЕФЕСТ"}, HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": f"Task {task_id} blocked"}

    elif cmd == "unblock" and len(args) == 1:
        task_id = args[0]
        resp = await services.call_handover("POST", "/unblock", {"task_id": task_id, "actor": "ГЕФЕСТ"}, HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": f"Task {task_id} unblocked"}

    elif cmd == "status":
        resp = await services.call_handover("GET", "/tasks", base_url=HANDOVER_URL)
        if "error" in resp:
            result = {"success": False, "output": resp["error"]}
        else:
            result = {"success": True, "output": json.dumps(resp, indent=2, ensure_ascii=False)}

    else:
        result = {"success": False, "output": f"Unknown command: {command}"}

    asyncio.create_task(send_log_to_br18("command_executed", {
        "command": command,
        "success": result["success"],
        "output": result["output"]
    }))

    return result


app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def index():
    """Главная страница консоли."""
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())