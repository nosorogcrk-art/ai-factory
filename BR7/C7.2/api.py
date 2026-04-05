import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import handover

app = FastAPI(title="Handover API")

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