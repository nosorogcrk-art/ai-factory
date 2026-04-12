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
        # Парсим L2 из строки JSON
        import json
        l2_data = json.loads(request.description)
        # Вызываем новую цепочку проектирования
        result = await services.decompose_l2(l2_data)
        
        # Извлекаем ID патчей для обратной совместимости
        patches_ids = [p.get("id") for p in result.get("patches", []) if isinstance(p, dict) and "id" in p]
        # Если нет ID, используем исходные patches (уже строки)
        if not patches_ids:
            patches_ids = result.get("patches", [])
        
        # Отправляем событие в BR18
        send_log_to_br18("decompose_success", {
            "description": request.description[:200],
            "patches": patches_ids,
            "branches": result.get("branches", []),
            "containers": result.get("containers", []),
            "queue": result.get("queue", []),
            "context": request.context
        })
        
        return models.DecomposeResponse(
            patches=patches_ids,
            branches=result.get("branches"),
            containers=result.get("containers"),
            queue=result.get("queue"),
            status="ok"
        )
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in description: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON in description"
        )
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
