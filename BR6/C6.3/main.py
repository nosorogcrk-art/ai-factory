import os
import logging
from fastapi import FastAPI, HTTPException, Query
import database
import limits
from models import CostReport, CheckRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Token Guard", version="1.0.0")

@app.on_event("startup")
def startup():
    database.init_db()
    # загружаем конфигурацию (она может отсутствовать – будет использована дефолтная)
    limits.load_config()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/report")
def report_cost(report: CostReport):
    try:
        database.insert_report(report)
        return {"status": "accepted"}
    except Exception as e:
        logger.error(f"Failed to insert report: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/check")
def check_limit(
    agent: str = Query(..., description="Agent name"),
    model: str = Query(..., description="Model to use"),
    estimated_tokens: int = Query(0, description="Estimated tokens to be used"),
    branch: str = Query(None, description="Branch name"),
    task_id: str = Query(None, description="Task ID")
):
    try:
        allowed, suggested, reason = limits.check_limit(agent, model, estimated_tokens, branch, task_id)
        return {"allowed": allowed, "suggested_model": suggested, "reason": reason}
    except Exception as e:
        logger.error(f"Check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Административные эндпоинты (для P6.3.5 позже)
@app.get("/limits")
def get_limits():
    return limits.load_config()

@app.put("/limits")
def update_limits(config: dict):
    try:
        limits.save_config(config)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
