import os
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel
import models
import services

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/patch_architect.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Patch Architect", version="1.0.0")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/decompose", status_code=status.HTTP_200_OK, response_model=models.DecomposeResponse)
async def decompose(request: models.DecomposeRequest) -> models.DecomposeResponse:
    if not request.description.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="description must not be empty"
        )

    try:
        patches = services.decompose_task(request.description, request.context)
        return models.DecomposeResponse(patches=patches)
    except Exception as e:
        logger.error(f"Decomposition failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during decomposition"
        )


class DecomposeRequest(BaseModel):
    description: str
    context: dict = {}


@app.post("/api/decompose")
async def decompose(req: DecomposeRequest):
    return {"patches": ["IMP-001"], "status": "ok"}
