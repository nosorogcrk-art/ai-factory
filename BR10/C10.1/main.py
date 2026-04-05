import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
import models
import services

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/integrator.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Integrator", version="0.3.0")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/build", response_model=models.BuildResponse)
async def build(req: models.BuildRequest, background_tasks: BackgroundTasks):
    logger.info(f"Build request for task {req.task_id}, patches: {req.patch_ids}")
    success, message = services.build_patches(req.task_id, req.patch_ids, req.check_skills, req.run_tests)
    if not success:
        raise HTTPException(status_code=500, detail=message)
    return models.BuildResponse(status="started", message=message)