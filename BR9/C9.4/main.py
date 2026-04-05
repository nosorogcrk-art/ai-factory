import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import models, services, repositories

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/dialogue_manager.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Dialogue Manager", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    repositories.init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/dialog", response_model=models.DialogResponse)
async def dialog(req: models.DialogRequest, background_tasks: BackgroundTasks):
    try:
        reply, completed, task_id, task_description = await services.process_dialog(req.project_id, req.message)
        if completed and task_id and task_description:
            background_tasks.add_task(services.background_processing, req.project_id, task_description, task_id)
    except Exception as e:
        logger.error(f"Dialog processing failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    return models.DialogResponse(
        session_id=req.project_id,
        reply=reply,
        completed=completed,
        task_id=task_id if completed else None
    )