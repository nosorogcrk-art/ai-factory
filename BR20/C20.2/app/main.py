import logging
from typing import List

from fastapi import FastAPI, HTTPException, status, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.models.config import (
    ConfigCreate, ConfigResponse, ConfigContentResponse,
    ConfigDiffResponse, RollbackRequest, HealthResponse
)
from app.services.config_service import ConfigService


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Создание FastAPI приложения
app = FastAPI(
    title="C20.2 Config Versioning API",
    description="API для управления версиями конфигураций",
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
config_service = ConfigService()


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Проверка здоровья сервиса
    
    Returns:
        Информация о состоянии сервиса
    """
    logger.info("Health check requested")
    
    health_data = config_service.health_check()
    
    return HealthResponse(
        status="ok",
        version_count=health_data["version_count"],
        database_status=health_data["database_status"],
        timestamp=health_data["timestamp"]
    )


@app.post("/configs", response_model=ConfigContentResponse, status_code=status.HTTP_201_CREATED, tags=["Configs"])
async def create_config(config_data: ConfigCreate) -> ConfigContentResponse:
    """
    Создание новой версии конфигурации
    
    Args:
        config_data: Данные для создания конфигурации
        
    Returns:
        Созданная конфигурация
    """
    try:
        config = config_service.create_config(config_data)
        return config
    except ValueError as e:
        logger.error(f"Ошибка создания конфигурации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Внутренняя ошибка при создании конфигурации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/configs", response_model=List[ConfigResponse], tags=["Configs"])
async def get_all_configs(
    limit: int = Query(100, ge=1, le=1000, description="Максимальное количество записей"),
    offset: int = Query(0, ge=0, description="Смещение")
) -> List[ConfigResponse]:
    """
    Получение списка всех конфигураций (без содержимого)
    
    Args:
        limit: Максимальное количество записей
        offset: Смещение
        
    Returns:
        Список конфигураций
    """
    try:
        configs = config_service.get_all_configs(limit, offset)
        return configs
    except Exception as e:
        logger.error(f"Ошибка получения списка конфигураций: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/configs/versions", response_model=List[str], tags=["Configs"])
async def get_config_versions() -> List[str]:
    """
    Получение списка всех версий конфигураций
    
    Returns:
        Список версий
    """
    try:
        versions = config_service.get_config_versions()
        return versions
    except Exception as e:
        logger.error(f"Ошибка получения списка версий: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/configs/latest", response_model=ConfigContentResponse, tags=["Configs"])
async def get_latest_config() -> ConfigContentResponse:
    """
    Получение последней версии конфигурации
    
    Returns:
        Последняя конфигурация
    """
    try:
        config = config_service.get_latest_config()
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Конфигурации не найдены"
            )
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения последней конфигурации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/configs/diff", response_model=ConfigDiffResponse, tags=["Configs"])
async def get_config_diff(
    from_version: str = Query(..., description="Исходная версия"),
    to_version: str = Query(..., description="Целевая версия")
) -> ConfigDiffResponse:
    """
    Получение разницы между двумя версиями конфигураций
    
    Args:
        from_version: Исходная версия
        to_version: Целевая версия
        
    Returns:
        Разница между версиями
    """
    try:
        diff = config_service.get_diff(from_version, to_version)
        if not diff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Одна или обе версии не найдены"
            )
        return diff
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения разницы: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.get("/configs/{version}", response_model=ConfigContentResponse, tags=["Configs"])
async def get_config_by_version(version: str) -> ConfigContentResponse:
    """
    Получение конфигурации по версии
    
    Args:
        version: Версия конфигурации
        
    Returns:
        Конфигурация
    """
    try:
        config = config_service.get_config(version)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Конфигурация с версией '{version}' не найдена"
            )
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения конфигурации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.delete("/configs/{version}", status_code=status.HTTP_204_NO_CONTENT, tags=["Configs"])
async def delete_config(version: str):
    """
    Удаление конфигурации по версии
    
    Args:
        version: Версия для удаления
    """
    try:
        deleted = config_service.delete_config(version)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Конфигурация с версией '{version}' не найдена"
            )
        return JSONResponse(status_code=status.HTTP_204_NO_CONTENT, content=None)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка удаления конфигурации: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера"
        )


@app.post("/configs/rollback/{version}", response_model=ConfigContentResponse, tags=["Configs"])
async def rollback_to_version(
    version: str,
    rollback_request: RollbackRequest
) -> ConfigContentResponse:
    """
    Откат к указанной версии конфигурации
    
    Args:
        version: Версия для отката
        rollback_request: Параметры отката
        
    Returns:
        Новая версия конфигурации после отката
    """
    try:
        # Используем версию из пути, если не указана в теле запроса
        if not rollback_request.target_version:
            rollback_request.target_version = version
        
        config = config_service.rollback_to_version(rollback_request)
        if not config:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Целевая версия '{rollback_request.target_version}' не найдена"
            )
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка отката: {str(e)}")
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
    uvicorn.run(app, host="0.0.0.0", port=8202)