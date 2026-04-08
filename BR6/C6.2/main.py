import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException

from .models import ReviewRequest, ReviewResponse, HealthResponse
from .services import SemanticAuditor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Клиент для отправки логов в BR18
BR18_URL = "http://br18-log-aggregator:8103/logs"  # Примерный URL, нужно уточнить


async def send_log_to_br18(event_type: str, details: dict):
    """Отправляет лог в BR18 (асинхронно)"""
    try:
        log_entry = {
            "timestamp": "2026-04-05T18:00:00Z",  # TODO: использовать реальное время
            "service": "C6.2",
            "event_type": event_type,
            "details": details
        }
        
        # В реальной реализации здесь будет асинхронный HTTP-запрос
        # async with httpx.AsyncClient() as client:
        #     await client.post(BR18_URL, json=log_entry, timeout=5.0)
        
        logger.info(f"Лог отправлен в BR18: {event_type} - {details}")
    except Exception as e:
        logger.error(f"Ошибка при отправке лога в BR18: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Контекст жизненного цикла приложения"""
    # Инициализация при запуске
    logger.info("Semantic Auditor C6.2 запускается...")
    yield
    # Очистка при остановке
    logger.info("Semantic Auditor C6.2 останавливается...")


app = FastAPI(
    title="Semantic Auditor C6.2",
    description="Семантический аудитор для проверки кода на соответствие Золотому стандарту",
    version="1.0.0",
    lifespan=lifespan
)

auditor = SemanticAuditor()


@app.get("/")
async def root():
    """Корневой эндпоинт"""
    return {
        "service": "Semantic Auditor C6.2",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Healthcheck эндпоинт"""
    return HealthResponse(status="ok")


@app.post("/review", response_model=ReviewResponse)
async def review_file(request: ReviewRequest):
    """Проверяет файл на соответствие Золотому стандарту"""
    try:
        logger.info(f"Запрос на проверку файла: {request.file_path}")
        
        # Выполняем проверку
        response = await auditor.review_file(request.file_path, request.content)
        
        # Логируем результат
        log_details = {
            "file_path": request.file_path,
            "status": response.status,
            "violations_count": len(response.violations),
            "has_errors": any(v.severity == "error" for v in response.violations)
        }
        
        # Отправляем лог в BR18 асинхронно (не блокируя ответ)
        # asyncio.create_task(send_log_to_br18("review_completed", log_details))
        
        logger.info(f"Проверка завершена: {response.status}, нарушений: {len(response.violations)}")
        return response
        
    except Exception as e:
        logger.error(f"Ошибка при проверке файла: {e}")
        raise HTTPException(status_code=500, detail=f"Внутренняя ошибка сервера: {str(e)}")


@app.get("/rules")
async def get_rules():
    """Возвращает список правил проверки"""
    return {
        "rules": [
            {
                "name": "has_tests",
                "description": "Проверяет наличие папки tests и файлов test_*.py",
                "severity": "error"
            },
            {
                "name": "has_healthcheck",
                "description": "Проверяет наличие эндпоинта /health",
                "severity": "error"
            },
            {
                "name": "has_passport",
                "description": "Проверяет наличие паспорта контейнера (.md файл)",
                "severity": "error"
            },
            {
                "name": "mypy_compliance",
                "description": "Проверяет типизацию с помощью mypy",
                "severity": "warning"
            },
            {
                "name": "ruff_compliance",
                "description": "Проверяет стиль кода с помощью ruff",
                "severity": "warning"
            }
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8106)  # Порт для C6.2