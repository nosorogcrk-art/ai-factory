import uuid
import os
import logging
import httpx
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from typing import Optional, List
import database
import models

LOG_FILE = "/app/logs/skill_registry.log"
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(title="Skill Registry", version="1.1.0")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

async def send_log_to_br18(event_type: str, details: dict):
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": "C17.1",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
            logger.info(f"Log sent to BR18: {event_type}")
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

@app.on_event("startup")
def startup():
    database.init_db()
    logger.info("Skill Registry started")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/skills/stats")
def get_stats():
    return database.get_stats()

@app.post("/skills", response_model=models.SkillInDB)
def create_skill(skill: models.SkillCreate, background_tasks: BackgroundTasks):
    skill_id = f"SKILL-{str(uuid.uuid4())[:8].upper()}"
    now = datetime.now(timezone.utc).isoformat()
    new_skill = models.SkillInDB(
        id=skill_id,
        created_at=now,
        updated_at=now,
        soft_deleted=False,
        **skill.model_dump()
    )
    database.create_skill(new_skill.model_dump())
    background_tasks.add_task(send_log_to_br18, "skill_created", {"skill_id": skill_id, "name": skill.name})
    return new_skill

@app.get("/skills", response_model=List[models.SkillInDB])
def list_skills(
    include_deleted: bool = Query(False),
    status: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    filters = {}
    if status:
        filters['status'] = status
    if tag:
        filters['tags'] = [tag]
    skills = database.get_all_skills(include_deleted, filters, limit, offset)
    return [models.SkillInDB(**s) for s in skills]

@app.get("/skills/{skill_id}", response_model=models.SkillInDB)
def get_skill(skill_id: str):
    skill = database.get_skill(skill_id)
    if not skill or skill.get("soft_deleted"):
        raise HTTPException(status_code=404, detail="Skill not found")
    return models.SkillInDB(**skill)

@app.put("/skills/{skill_id}", response_model=models.SkillInDB)
def update_skill(skill_id: str, update: models.SkillUpdate, background_tasks: BackgroundTasks):
    existing = database.get_skill(skill_id)
    if not existing or existing.get("soft_deleted"):
        raise HTTPException(status_code=404, detail="Skill not found")
    update_data = update.model_dump(exclude_unset=True)
    database.update_skill(skill_id, update_data)
    updated = database.get_skill(skill_id)
    background_tasks.add_task(send_log_to_br18, "skill_updated", {"skill_id": skill_id, "changed_fields": list(update_data.keys())})
    return models.SkillInDB(**updated)

@app.patch("/skills/{skill_id}", response_model=models.SkillInDB)
def patch_skill(skill_id: str, update: models.SkillUpdate, background_tasks: BackgroundTasks):
    existing = database.get_skill(skill_id)
    if not existing or existing.get("soft_deleted"):
        raise HTTPException(status_code=404, detail="Skill not found")
    update_data = update.model_dump(exclude_unset=True)
    database.update_skill(skill_id, update_data)
    updated = database.get_skill(skill_id)
    background_tasks.add_task(send_log_to_br18, "skill_updated", {"skill_id": skill_id, "changed_fields": list(update_data.keys())})
    return models.SkillInDB(**updated)

@app.delete("/skills/{skill_id}")
def delete_skill(skill_id: str, hard: bool = Query(False), background_tasks: BackgroundTasks = None):
    existing = database.get_skill(skill_id)
    if not existing or existing.get("soft_deleted"):
        raise HTTPException(status_code=404, detail="Skill not found")
    database.delete_skill(skill_id, hard)
    if background_tasks:
        background_tasks.add_task(send_log_to_br18, "skill_deleted", {"skill_id": skill_id, "hard": hard})
    return {"message": "Skill deleted" if hard else "Skill soft-deleted"}