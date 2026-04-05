import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import models
import services
import repositories

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/gitops_core.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="GitOps Core", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

repositories.init_db()

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook(payload: dict, background_tasks: BackgroundTasks):
    ref = payload.get("ref", "")
    if not ref.endswith("/main"):
        return {"message": "Ignoring non-main branch push"}
    repo_url = payload.get("repository", {}).get("clone_url")
    if not repo_url:
        raise HTTPException(status_code=400, detail="Missing repository URL")
    branch = "main"
    job_id = f"deploy_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    deployment = {
        "id": job_id,
        "status": "pending",
        "started_at": now,
        "finished_at": None,
        "repo_url": repo_url,
        "branch": branch,
        "version": None,
        "log": None
    }
    repositories.save_deployment(deployment)
    background_tasks.add_task(services.perform_deployment, job_id, repo_url, branch)
    return {"job_id": job_id, "status": "started"}

@app.post("/deploy")
async def deploy(req: models.DeployRequest, background_tasks: BackgroundTasks):
    job_id = f"deploy_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    deployment = {
        "id": job_id,
        "status": "pending",
        "started_at": now,
        "finished_at": None,
        "repo_url": req.repo_url,
        "branch": req.branch,
        "version": req.version,
        "log": None
    }
    repositories.save_deployment(deployment)
    background_tasks.add_task(services.perform_deployment, job_id, req.repo_url, req.branch, req.version)
    return {"job_id": job_id, "status": "started"}

@app.get("/deployments")
async def list_deployments(limit: int = 10, offset: int = 0):
    deployments = repositories.list_deployments(limit, offset)
    return {"deployments": deployments}

@app.get("/deployments/{deployment_id}/status")
async def deployment_status(deployment_id: str):
    dep = repositories.get_deployment(deployment_id)
    if not dep:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return dep