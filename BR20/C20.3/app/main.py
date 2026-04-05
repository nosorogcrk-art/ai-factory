import logging
from typing import List

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.models.deployment import (
    DeploymentCreate, DeploymentResponse, RollbackRequest, RollbackResponse,
    AlertNotification, HealthResponse
)
from app.services.rollback_service import RollbackService


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="C20.3 Rollback Manager API",
    description="API для управления откатами в системе CI/CD завода агентов ИИ",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация сервиса
rollback_service = RollbackService()


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Проверка здоровья сервиса
    
    Returns:
        Информация о состоянии сервиса
    """
    logger.info("Health check requested")
    
    health_data = rollback_service.health_check()
    
    return HealthResponse(
        status=health_data.status,
        deployment_count=health_data.deployment_count,
        rollback_count=health_data.rollback_count,
        database_status=health_data.database_status,
        timestamp=health_data.timestamp
    )


@app.post("/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED, tags=["Deployments"])
async def record_deployment(deployment: DeploymentCreate) -> DeploymentResponse:
    """
    Запись информации о деплое
    
    Args:
        deployment: Данные о деплое
        
    Returns:
        Информация о сохраненном деплое
    """
    try:
        result = await rollback_service.record_deployment(deployment)
        return result
    except ValueError as e:
        logger.error(f"Ошибка записи деплоя: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Внутренняя ошибка при записи деплоя: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/deployments", response_model=List[DeploymentResponse], tags=["Deployments"])
async def get_deployments(
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    environment: str = Query(None, description="Фильтр по окружению")
) -> List[DeploymentResponse]:
    """
    Получение списка деплоев
    
    Args:
        limit: Максимальное количество записей
        offset: Смещение
        environment: Фильтр по окружению
        
    Returns:
        Список деплоев
    """
    try:
        deployments = rollback_service.get_deployments(limit, offset, environment)
        return deployments
    except Exception as e:
        logger.error(f"Ошибка получения списка деплоев: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/deployments/latest", response_model=DeploymentResponse, tags=["Deployments"])
async def get_latest_deployment(
    environment: str = Query(None, description="Окружение")
) -> DeploymentResponse:
    """
    Получение последнего деплоя
    
    Args:
        environment: Окружение (опционально)
        
    Returns:
        Последний деплой
    """
    try:
        deployment = rollback_service.get_latest_deployment(environment)
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Деплои не найдены"
            )
        return deployment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения последнего деплоя: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/deployments/{deploy_id}", response_model=DeploymentResponse, tags=["Deployments"])
async def get_deployment_by_id(deploy_id: str) -> DeploymentResponse:
    """
    Получение информации о деплое по ID
    
    Args:
        deploy_id: ID деплоя
        
    Returns:
        Информация о деплое
    """
    try:
        deployment = rollback_service.get_deployment_by_id(deploy_id)
        if not deployment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Деплой с ID '{deploy_id}' не найден"
            )
        return deployment
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения деплоя: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.post("/rollback", response_model=RollbackResponse, tags=["Rollback"])
async def execute_rollback(rollback_request: RollbackRequest) -> RollbackResponse:
    """
    Выполнение отката
    
    Args:
        rollback_request: Запрос на откат
        
    Returns:
        Информация об инициированном откате
    """
    try:
        result = await rollback_service.execute_rollback(rollback_request)
        return result
    except ValueError as e:
        logger.error(f"Ошибка выполнения отката: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Внутренняя ошибка при выполнении отката: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/rollback/history", response_model=List, tags=["Rollback"])
async def get_rollback_history(
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    offset: int = Query(0, ge=0, description="Смещение")
) -> List:
    """
    Получение истории откатов
    
    Args:
        limit: Максимальное количество записей
        offset: Смещение
        
    Returns:
        Список откатов
    """
    try:
        rollbacks = rollback_service.get_rollback_history(limit, offset)
        return rollbacks
    except Exception as e:
        logger.error(f"Ошибка получения истории откатов: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/rollback/{rollback_id}", response_model=dict, tags=["Rollback"])
async def get_rollback_by_id(rollback_id: str) -> dict:
    """
    Получение информации об откате по ID
    
    Args:
        rollback_id: ID отката
        
    Returns:
        Информация об откате
    """
    try:
        rollback = rollback_service.get_rollback_by_id(rollback_id)
        if not rollback:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Откат с ID '{rollback_id}' не найден"
            )
        return rollback.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения отката: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.post("/alerts", status_code=status.HTTP_202_ACCEPTED, tags=["Alerts"])
async def handle_alert_notification(alert: AlertNotification) -> dict:
    """
    Обработка уведомления от Alert Manager (BR18)
    
    Args:
        alert: Уведомление об алерте
        
    Returns:
        Результат обработки алерта
    """
    try:
        rollback_id = await rollback_service.handle_alert_notification(alert)
        
        if rollback_id:
            return {
                "status": "rollback_triggered",
                "rollback_id": rollback_id,
                "message": f"Откат инициирован: {rollback_id}"
            }
        else:
            return {
                "status": "no_action_required",
                "message": "Откат не требуется"
            }
    except Exception as e:
        logger.error(f"Ошибка обработки алерта: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Обработчик исключений HTTP"""
    logger.error(f"HTTP ошибка {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Обработчик общих исключений"""
    logger.error(f"Необработанное исключение: {str(exc)}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Внутренняя ошибка сервера"},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8203)
