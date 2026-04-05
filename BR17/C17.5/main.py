import os
import time
import logging
import httpx
from datetime import datetime, timezone
from typing import List, Optional, Dict
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import models
import services
import repositories as cache_repo

LOG_FILE = "/app/logs/skill_publisher.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Skill Publisher", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    async def _send():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    BR18_URL,
                    json={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": "C17.5",
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

@app.get("/status")
def status():
    return models.StatusResponse(
        status="ok",
        cache_stats=cache_repo.get_cache_stats()
    )

@app.get("/skill/{skill_id}")
async def get_skill(skill_id: str, version: Optional[str] = None, agent_type: str = "main", background_tasks: BackgroundTasks = None):
    start = time.time()
    skill = await services.get_skill(skill_id, version, agent_type)
    duration_ms = (time.time() - start) * 1000
    if background_tasks is not None:
        await send_log_to_br18("skill_published", {
            "skill_id": skill_id,
            "version": version or "latest",
            "agent_type": agent_type,
            "cached": skill is not None and "cache_hit" in str(skill),
            "response_time_ms": round(duration_ms, 2)
        }, background_tasks)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found or access denied")
    return skill

@app.post("/skills/batch")
async def batch_skills(request: models.BatchRequest, background_tasks: BackgroundTasks = None):
    start = time.time()
    results = []
    for skill_id in request.skills:
        skill = await services.get_skill(skill_id, version=None, agent_type=request.agent_type)
        results.append(skill if skill else None)
    duration_ms = (time.time() - start) * 1000
    if background_tasks is not None:
        await send_log_to_br18("batch_request", {
            "skills_count": len(request.skills),
            "response_time_ms": round(duration_ms, 2)
        }, background_tasks)
    return results