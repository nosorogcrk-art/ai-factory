"""
Основной файл FastAPI приложения для C20.4 Test Runner
"""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import JSONResponse

from app.models.config import (
    TestRequest, TestResponse, TestResultsResponse,
    TestStatus, HealthResponse
)
from app.services.test_service import TestService
from app.repositories.test_repository import TestRepository

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация сервисов
test_service = TestService()
test_repository = TestRepository()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Управление жизненным циклом приложения"""
    logger.info("Starting C20.4 Test Runner...")
    yield
    logger.info("Shutting down C20.4 Test Runner...")
    await test_service.close()


# Создание FastAPI приложения
app = FastAPI(
    title="C20.4 Test Runner",
    description="Сервис для автоматического тестирования конфигураций перед деплоем",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Проверка здоровья сервиса
    
    Returns:
        HealthResponse: Статус здоровья сервиса
    """
    is_healthy = await test_service.health_check()
    status = "healthy" if is_healthy else "unhealthy"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.now()
    )


@app.post("/test", response_model=TestResponse)
async def run_tests(test_request: TestRequest):
    """
    Запуск тестов для указанного репозитория и коммита
    
    Args:
        test_request (TestRequest): Запрос на запуск тестов
        
    Returns:
        TestResponse: Информация о запущенном тесте
    """
    try:
        # Запускаем тесты
        test_response = await test_service.run_tests(test_request)
        
        # Сохраняем информацию о тесте в БД
        test_repository.save_test(test_response)
        
        logger.info(f"Test {test_response.test_id} started for repo {test_request.repo}")
        return test_response
        
    except Exception as e:
        logger.error(f"Failed to start tests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start tests: {str(e)}")


@app.get("/results/{test_id}", response_model=TestResultsResponse)
async def get_test_results(test_id: str):
    """
    Получение результатов тестов по ID
    
    Args:
        test_id (str): ID теста
        
    Returns:
        TestResultsResponse: Результаты тестов
    """
    # Пытаемся получить результаты из сервиса
    results = await test_service.get_test_results(test_id)
    
    if not results:
        # Если нет в сервисе, ищем в БД
        results = test_repository.get_test(test_id)
    
    if not results:
        raise HTTPException(status_code=404, detail=f"Test {test_id} not found")
    
    return results


@app.get("/tests/recent", response_model=list[TestResultsResponse])
async def get_recent_tests(limit: int = 10):
    """
    Получение списка последних тестов
    
    Args:
        limit (int): Количество тестов для возврата (по умолчанию 10)
        
    Returns:
        List[TestResultsResponse]: Список последних тестов
    """
    try:
        tests = test_repository.get_recent_tests(limit)
        return tests
    except Exception as e:
        logger.error(f"Failed to get recent tests: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get recent tests: {str(e)}")


@app.post("/tests/{test_id}/cancel")
async def cancel_test(test_id: str):
    """
    Отмена выполнения теста
    
    Args:
        test_id (str): ID теста для отмены
        
    Returns:
        dict: Статус операции
    """
    try:
        # Получаем тест из БД
        test = test_repository.get_test(test_id)
        
        if not test:
            raise HTTPException(status_code=404, detail=f"Test {test_id} not found")
        
        if test.status not in [TestStatus.PENDING, TestStatus.RUNNING]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel test with status {test.status.value}"
            )
        
        # Обновляем статус теста
        test.status = TestStatus.FAILED
        test.completed_at = datetime.now()
        
        # Обновляем в БД
        test_repository.update_test_results(test_id, test)
        
        logger.info(f"Test {test_id} cancelled")
        return {"status": "success", "message": f"Test {test_id} cancelled"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel test {test_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel test: {str(e)}")


@app.get("/")
async def root():
    """
    Корневой эндпоинт
    
    Returns:
        dict: Информация о сервисе
    """
    return {
        "service": "C20.4 Test Runner",
        "version": "1.0.0",
        "description": "Сервис для автоматического тестирования конфигураций перед деплоем",
        "endpoints": {
            "health": "/health",
            "run_tests": "/test (POST)",
            "get_results": "/results/{test_id}",
            "recent_tests": "/tests/recent",
            "cancel_test": "/tests/{test_id}/cancel (POST)",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }


# Обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Глобальный обработчик исключений"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8204))
    uvicorn.run(app, host="0.0.0.0", port=port)