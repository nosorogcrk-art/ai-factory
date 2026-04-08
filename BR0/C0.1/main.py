import logging
from datetime import datetime
from typing import List

from fastapi import FastAPI, HTTPException, BackgroundTasks

from .models import (
    ContainerInfo,
    ContainerActionRequest,
    ContainerActionResponse,
    HealthCheckResponse,
    ContainerStatus
)
from .services import docker_service, logging_service


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("01_ЦЕХ/01_ЖУРНАЛЫ/C0.1.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаём FastAPI приложение
app = FastAPI(
    title="C0.1 - Оркестратор среды (Гермес)",
    description="Управление Docker-контейнерами завода",
    version="1.0.0"
)

# Глобальные переменные
start_time = datetime.now()


@app.get("/health", response_model=HealthCheckResponse)
async def health_check() -> HealthCheckResponse:
    """Healthcheck эндпоинт для самого Гермеса"""
    try:
        # Проверяем доступность Docker демона
        docker_available = docker_service.check_docker_daemon()
        
        # Получаем информацию о контейнерах
        containers = docker_service.list_containers(all_containers=True)
        running_containers = [c for c in containers if c.status == ContainerStatus.RUNNING]
        
        # Определяем общий статус
        status = "healthy" if docker_available else "unhealthy"
        
        return HealthCheckResponse(
            status=status,
            timestamp=datetime.now().isoformat(),
            uptime=(datetime.now() - start_time).total_seconds(),
            docker_daemon=docker_available,
            containers_running=len(running_containers),
            containers_total=len(containers)
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthCheckResponse(
            status="unhealthy",
            timestamp=datetime.now().isoformat(),
            uptime=(datetime.now() - start_time).total_seconds(),
            docker_daemon=False,
            containers_running=0,
            containers_total=0
        )


@app.get("/containers", response_model=List[ContainerInfo])
async def list_containers(all: bool = False) -> List[ContainerInfo]:
    """Получить список всех контейнеров"""
    try:
        containers = docker_service.list_containers(all_containers=all)
        return containers
    except Exception as e:
        logger.error(f"Failed to list containers: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list containers: {str(e)}")


@app.get("/containers/{container_name}/status", response_model=ContainerInfo)
async def get_container_status(container_name: str) -> ContainerInfo:
    """Получить статус конкретного контейнера"""
    try:
        container_info = docker_service.get_container_status(container_name)
        return container_info
    except Exception as e:
        logger.error(f"Failed to get status for container {container_name}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status for container {container_name}: {str(e)}"
        )


@app.post("/containers/{container_name}/start", response_model=ContainerActionResponse)
async def start_container(
    container_name: str,
    request: ContainerActionRequest,
    background_tasks: BackgroundTasks
) -> ContainerActionResponse:
    """Запустить контейнер"""
    try:
        # Выполняем действие
        response = docker_service.start_container(
            container_name=container_name,
            force=request.force
        )
        
        # Логируем действие в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="start",
            success=response.success,
            message=response.message
        )
        
        return response
    except Exception as e:
        error_message = f"Failed to start container {container_name}: {str(e)}"
        logger.error(error_message)
        
        # Логируем ошибку в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="start",
            success=False,
            message=error_message
        )
        
        raise HTTPException(status_code=500, detail=error_message)


@app.post("/containers/{container_name}/stop", response_model=ContainerActionResponse)
async def stop_container(
    container_name: str,
    request: ContainerActionRequest,
    background_tasks: BackgroundTasks
) -> ContainerActionResponse:
    """Остановить контейнер"""
    try:
        # Выполняем действие
        response = docker_service.stop_container(
            container_name=container_name,
            timeout=request.timeout
        )
        
        # Логируем действие в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="stop",
            success=response.success,
            message=response.message
        )
        
        return response
    except Exception as e:
        error_message = f"Failed to stop container {container_name}: {str(e)}"
        logger.error(error_message)
        
        # Логируем ошибку в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="stop",
            success=False,
            message=error_message
        )
        
        raise HTTPException(status_code=500, detail=error_message)


@app.post("/containers/{container_name}/restart", response_model=ContainerActionResponse)
async def restart_container(
    container_name: str,
    request: ContainerActionRequest,
    background_tasks: BackgroundTasks
) -> ContainerActionResponse:
    """Перезапустить контейнер"""
    try:
        # Выполняем действие
        response = docker_service.restart_container(
            container_name=container_name,
            timeout=request.timeout
        )
        
        # Логируем действие в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="restart",
            success=response.success,
            message=response.message
        )
        
        return response
    except Exception as e:
        error_message = f"Failed to restart container {container_name}: {str(e)}"
        logger.error(error_message)
        
        # Логируем ошибку в фоне
        background_tasks.add_task(
            logging_service.log_container_action,
            container_name=container_name,
            action="restart",
            success=False,
            message=error_message
        )
        
        raise HTTPException(status_code=500, detail=error_message)


@app.get("/")
async def root():
    """Корневой эндпоинт с информацией о сервисе"""
    return {
        "service": "C0.1 - Оркестратор среды (Гермес)",
        "version": "1.0.0",
        "description": "Управление Docker-контейнерами завода",
        "endpoints": {
            "health": "/health",
            "list_containers": "/containers",
            "container_status": "/containers/{name}/status",
            "start_container": "/containers/{name}/start",
            "stop_container": "/containers/{name}/stop",
            "restart_container": "/containers/{name}/restart"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8100)