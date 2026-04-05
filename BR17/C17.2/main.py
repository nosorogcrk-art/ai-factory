import os
import logging
from fastapi import FastAPI, HTTPException, BackgroundTasks
import database

LOG_FILE = "/app/logs/skill_version_control.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Skill Version Control", version="1.0.0")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks):
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    async def _send():
        import httpx
        from datetime import datetime, timezone
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    BR18_URL,
                    json={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": "C17.2",
                        "event_type": event_type,
                        "details": details
                    },
                    timeout=5.0
                )
                logger.info(f"Log sent to BR18: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")
    background_tasks.add_task(_send)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/commit/{skill_id}")
def commit_skill(skill_id: str, req: dict, background_tasks: BackgroundTasks):
    content = req.get("content")
    message = req.get("message")
    if not content or not message:
        raise HTTPException(status_code=400, detail="Missing content or message")
    try:
        commit_hash = database.commit_skill(skill_id, content, message)
        background_tasks.add_task(send_log_to_br18, "commit_created", {
            "skill_id": skill_id,
            "commit_hash": commit_hash,
            "message": message
        }, background_tasks)
        return {"commit_hash": commit_hash}
    except Exception as e:
        logger.error(f"Commit failed: {e}")
        background_tasks.add_task(send_log_to_br18, "commit_failed", {
            "skill_id": skill_id,
            "error": str(e)
        }, background_tasks)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{skill_id}")
def get_history(skill_id: str):
    try:
        history = database.get_history(skill_id)
        return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/file/{skill_id}")
def get_file(skill_id: str, ref: str):
    try:
        content = database.get_file_content(skill_id, ref)
        if content is None:
            raise HTTPException(status_code=404, detail="File not found")
        return content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/diff/{skill_id}")
def get_diff(skill_id: str, from_hash: str, to_hash: str):
    try:
        diff = database.get_diff(skill_id, from_hash, to_hash)
        return {"diff": diff}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/rollback/{skill_id}")
def rollback_skill(skill_id: str, to_hash: str, background_tasks: BackgroundTasks):
    try:
        new_hash = database.rollback(skill_id, to_hash)
        background_tasks.add_task(send_log_to_br18, "rollback_performed", {
            "skill_id": skill_id,
            "to_hash": to_hash,
            "new_commit_hash": new_hash
        }, background_tasks)
        return {"new_commit_hash": new_hash}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))