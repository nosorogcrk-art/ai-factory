"""FastAPI application for Skill Tester (real Docker testing with BR18 logging)."""
import os
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import models
import services
import repositories

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/skill_tester.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    repositories.init_db()
    logger.info("Skill Tester started")
    yield
    services.close_docker_client()
    logger.info("Skill Tester shut down")

app = FastAPI(title="Skill Tester", version="0.5.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/status")
async def status():
    return {"status": "ok"}

@app.post("/test/{skill_id}", response_model=models.TestRunResponse)
async def test_skill(skill_id: str, background_tasks: BackgroundTasks):
    """Start a test for the given skill (real Docker execution) and return result."""
    logger.info(f"Test requested for skill {skill_id}")
    test_run_id, passed, output, duration, error = await services.start_test_real(skill_id, background_tasks)
    if error:
        raise HTTPException(status_code=404, detail=error)
    assert test_run_id is not None
    return models.TestRunResponse(
        test_run_id=test_run_id,
        skill_id=skill_id,
        status="completed",
        passed=passed,
        output=output,
        duration_seconds=duration
    )

@app.get("/results/{skill_id}", response_model=models.SkillTestResults)
async def get_results(skill_id: str):
    results = services.get_results(skill_id)
    return models.SkillTestResults(**results)

@app.post("/test/all")
async def test_all_skills():
    return {"status": "not_implemented", "message": "Will be implemented in later patches"}