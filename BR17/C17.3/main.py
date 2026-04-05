import os
import asyncio
import logging
import httpx
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, BackgroundTasks
from graph_builder import SkillGraph

SKILL_REGISTRY_URL = os.getenv("SKILL_REGISTRY_URL", "http://skill-registry:8088")
UPDATE_INTERVAL = int(os.getenv("UPDATE_INTERVAL", "3600"))
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

graph = SkillGraph(SKILL_REGISTRY_URL)

async def periodic_update():
    while True:
        await graph.update()
        await asyncio.sleep(UPDATE_INTERVAL)

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
                    "service": "C17.3",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
            logger.info(f"Log sent to BR18: {event_type}")
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_update())
    yield
    task.cancel()

app = FastAPI(title="Skill Graph", version="1.0.0", lifespan=lifespan)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/graph")
def get_graph():
    return graph.get_graph()

@app.get("/graph/{skill_id}")
def get_skill_info(skill_id: str):
    if skill_id not in graph.skills_meta:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {
        "skill": graph.skills_meta[skill_id],
        "dependencies": graph.outgoing.get(skill_id, [])
    }

@app.get("/dependencies/{skill_id}")
def get_dependencies(skill_id: str, transitive: bool = False):
    deps = graph.get_dependencies(skill_id, transitive)
    return {"dependencies": deps}

@app.get("/reverse-dependencies/{skill_id}")
def get_reverse_dependencies(skill_id: str):
    rev = graph.get_reverse_dependencies(skill_id)
    return {"reverse_dependencies": rev}

@app.get("/cycle-check")
async def cycle_check(background_tasks: BackgroundTasks):
    cycles = graph.detect_cycles()
    has_cycles = len(cycles) > 0
    if has_cycles:
        background_tasks.add_task(send_log_to_br18, "cycle_detected", {"cycles": cycles})
    return {"has_cycles": has_cycles, "cycles": cycles}