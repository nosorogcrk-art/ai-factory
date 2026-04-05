import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/pipeline_configurator.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

GITOPS_CORE_URL = os.getenv("GITOPS_CORE_URL", "http://gitops-core:8105")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))

app = FastAPI(title="Pipeline Configurator", version="0.1.0")
client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

@app.on_event("shutdown")
async def shutdown():
    await client.aclose()

@app.get("/health")
async def health():
    return {"status": "ok"}

class DeployRequest(BaseModel):
    type: str  # "prompt" или "skill"
    object_id: str
    version: str

@app.post("/deploy")
async def trigger_deploy(req: DeployRequest):
    """Активирует CI/CD через GitOps Core (C20.2)"""
    try:
        resp = await client.post(f"{GITOPS_CORE_URL}/deploy", json=req.dict())
        resp.raise_for_status()
        logger.info(f"Deploy triggered for {req.type}/{req.object_id} version {req.version}")
        return {"status": "triggered", "response": resp.json()}
    except Exception as e:
        logger.error(f"Failed to trigger deploy: {e}")
        raise HTTPException(status_code=503, detail=f"CI/CD unavailable: {e}")
