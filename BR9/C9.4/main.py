import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import httpx
import models
import services
import repositories

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
        
        # Проверяем, является ли ответ ошибкой "Проект не найден"
        if "Проект не найден" in reply:
            raise HTTPException(status_code=400, detail="Project not found")
        
        if completed and task_id and task_description:
            background_tasks.add_task(services.background_processing, req.project_id, task_description, task_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Dialog processing failed: {e}")
        raise HTTPException(status_code=503, detail=str(e))

    return models.DialogResponse(
        session_id=req.project_id,
        reply=reply,
        completed=completed,
        task_id=task_id if completed else None
    )


@app.post("/api/dialog/finish")
async def finish_dialog(request: dict):
    project_id = request.get("project_id")
    if not project_id:
        raise HTTPException(status_code=400, detail="Missing 'project_id'")
    
    try:
        history = await services.get_dialog_history(project_id)
        if not history:
            raise HTTPException(status_code=404, detail="No messages found for project")
        
        l2_data = await services.finalize_l2(project_id, history)
        result = await services.save_l2_artifact(project_id, l2_data)
        logger.info(f"L2 finalized for project {project_id}: {result}")
        return {"status": "ok", "l2": l2_data, "artifact": result}
    
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error while finalizing L2: {e}")
        raise HTTPException(status_code=502, detail=f"Upstream error: {e.response.text}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
