import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, status
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


def send_log_to_br18(event_type: str, data: dict) -> None:
    """
    Заглушка для отправки логов в BR18 (Monitoring).
    В будущем будет реализована интеграция с BR18.
    """
    logger.info(f"[BR18] {event_type}: {data}")
    # TODO: реализовать HTTP-вызов к BR18


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
        logger.info(f"Decompose request: {request.description[:100]}...")
        result = await services.decompose_task(request.description, request.context)
        
        # Отправляем событие в BR18
        send_log_to_br18("decompose_success", {
            "description": request.description[:200],
            "patches": result.get("patches", []),
            "branches": result.get("branches", []),
            "context": request.context
        })
        
        return models.DecomposeResponse(patches=result.get("patches", []), branches=result.get("branches", []))
    except Exception as e:
        logger.error(f"Decomposition failed: {e}")
        send_log_to_br18("decompose_error", {
            "error": str(e),
            "description": request.description[:200]
        })
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during decomposition"
        )
