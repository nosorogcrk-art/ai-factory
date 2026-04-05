import logging
import httpx
from typing import List, Optional
from datetime import datetime

from app.models.deployment import (
    DeploymentCreate, DeploymentResponse, RollbackRequest, RollbackResponse,
    RollbackStatus, AlertNotification, HealthResponse
)
from app.repositories.deployment_repository import DeploymentRepository


logger = logging.getLogger(__name__)


class RollbackService:
    """Сервисный слой для управления откатами"""
    
    def __init__(self, repository: Optional[DeploymentRepository] = None,
                 gitops_url: str = "http://gitops-core:8105",
                 env_manager_url: str = "http://environment-manager:8109",
                 alert_manager_url: str = "http://alert-manager:8118"):
        """Инициализация сервиса"""
        self.repository = repository or DeploymentRepository()
        self.gitops_url = gitops_url
        self.env_manager_url = env_manager_url
        self.alert_manager_url = alert_manager_url
    
    async def record_deployment(self, deployment: DeploymentCreate) -> DeploymentResponse:
        """
        Запись информации о деплое
        
        Args:
            deployment: Данные о деплое
            
        Returns:
            Информация о сохраненном деплое
            
        Raises:
            ValueError: Если deploy_id уже существует
        """
        logger.info(f"Recording deployment: {deployment.deploy_id}")
        
        deployment_id = self.repository.save_deployment(deployment)
        
        saved_deployment = self.repository.get_deployment_by_id(deployment.deploy_id)
        if not saved_deployment:
            raise RuntimeError(f"Failed to retrieve saved deployment: {deployment.deploy_id}")
        
        logger.info(f"Deployment recorded: {saved_deployment.deploy_id} (ID: {saved_deployment.id})")
        return saved_deployment
    
    def get_deployments(self, limit: int = 100, offset: int = 0,
                       environment: Optional[str] = None) -> List[DeploymentResponse]:
        """
        Получение списка деплоев
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение
            environment: Фильтр по окружению
            
        Returns:
            Список деплоев
        """
        logger.debug(f"Getting deployments (limit={limit}, offset={offset}, environment={environment})")
        return self.repository.get_deployments(limit, offset, environment)
    
    def get_deployment_by_id(self, deploy_id: str) -> Optional[DeploymentResponse]:
        """
        Получение информации о деплое по ID
        
        Args:
            deploy_id: ID деплоя
            
        Returns:
            Информация о деплое или None если не найден
        """
        logger.debug(f"Getting deployment: {deploy_id}")
        return self.repository.get_deployment_by_id(deploy_id)
    
    def get_latest_deployment(self, environment: Optional[str] = None) -> Optional[DeploymentResponse]:
        """
        Получение последнего деплоя
        
        Args:
            environment: Окружение (опционально)
            
        Returns:
            Последний деплой или None если нет деплоев
        """
        logger.debug(f"Getting latest deployment for environment: {environment}")
        return self.repository.get_latest_deployment(environment)
    
    async def execute_rollback(self, rollback_request: RollbackRequest) -> RollbackResponse:
        """
        Выполнение отката
        
        Args:
            rollback_request: Запрос на откат
            
        Returns:
            Информация об инициированном откате
        """
        logger.info(f"Executing rollback: {rollback_request}")
        
        # Определение целевого деплоя
        target_deployment = None
        
        if rollback_request.deploy_id:
            # Используем указанный deploy_id
            target_deployment = self.repository.get_deployment_by_id(rollback_request.deploy_id)
            if not target_deployment:
                raise ValueError(f"Deployment not found: {rollback_request.deploy_id}")
        elif rollback_request.environment:
            # Ищем последний деплой в указанном окружении
            target_deployment = self.repository.get_latest_deployment(rollback_request.environment)
            if not target_deployment:
                raise ValueError(f"No deployments found for environment: {rollback_request.environment}")
        else:
            raise ValueError("Either deploy_id or environment must be specified")
        
        # Определение целевой версии для отката
        target_version = rollback_request.target_version
        if not target_version:
            # Если версия не указана, используем предыдущий деплой
            previous_deployment = self.repository.get_previous_deployment(target_deployment.deploy_id)
            if not previous_deployment:
                raise ValueError(f"No previous deployment found for: {target_deployment.deploy_id}")
            target_version = previous_deployment.tag or previous_deployment.commit_hash
        
        # Создание записи об откате
        rollback_id = self.repository.create_rollback(
            deploy_id=target_deployment.deploy_id,
            target_version=target_version,
            reason=rollback_request.reason
        )
        
        # Обновление статуса отката
        self.repository.update_rollback_status(rollback_id, RollbackStatus.IN_PROGRESS)
        
        # Запуск асинхронного процесса отката
        import asyncio
        asyncio.create_task(self._perform_rollback_async(rollback_id, target_deployment, target_version))
        
        logger.info(f"Rollback initiated: {rollback_id}")
        
        return RollbackResponse(
            rollback_id=rollback_id,
            status=RollbackStatus.IN_PROGRESS,
            message="Rollback initiated",
            deploy_id=target_deployment.deploy_id,
            target_version=target_version,
            created_at=datetime.now()
        )
    
    async def _perform_rollback_async(self, rollback_id: str, 
                                    target_deployment: DeploymentResponse,
                                    target_version: str):
        """
        Асинхронное выполнение отката
        
        Args:
            rollback_id: ID отката
            target_deployment: Целевой деплой
            target_version: Целевая версия
        """
        try:
            logger.info(f"Starting rollback process: {rollback_id}")
            
            # 1. Получение файлов конфигурации из GitOps Core (C20.1)
            config_files = await self._get_config_files_from_gitops(
                target_deployment.repository,
                target_version
            )
            
            # 2. Применение конфигураций через Environment Manager (C20.5)
            await self._apply_configurations(
                target_deployment.environment,
                config_files
            )
            
            # 3. Обновление статуса отката
            self.repository.update_rollback_status(
                rollback_id, 
                RollbackStatus.COMPLETED,
                completed=True
            )
            
            # 4. Логирование успешного отката
            await self._log_rollback_success(rollback_id, target_deployment, target_version)
            
            logger.info(f"Rollback completed successfully: {rollback_id}")
            
        except Exception as e:
            logger.error(f"Rollback failed: {rollback_id}, error: {str(e)}")
            
            # Обновление статуса отката
            self.repository.update_rollback_status(
                rollback_id,
                RollbackStatus.FAILED,
                completed=True
            )
            
            # Логирование ошибки
            await self._log_rollback_failure(rollback_id, str(e))
    
    async def _get_config_files_from_gitops(self, repository: str, version: str) -> dict:
        """
        Получение файлов конфигурации из GitOps Core
        
        Args:
            repository: Название репозитория
            version: Версия (тег или коммит)
            
        Returns:
            Словарь с файлами конфигурации
        """
        logger.debug(f"Getting config files from GitOps: {repository}@{version}")
        
        # Здесь будет интеграция с C20.1 (GitOps Core)
        # Временная заглушка
        return {
            "docker-compose.yml": f"version: '3.8'\nservices:\n  app:\n    image: nginx:{version}",
            "config.env": f"VERSION={version}\nENVIRONMENT=production"
        }
    
    async def _apply_configurations(self, environment: str, config_files: dict):
        """
        Применение конфигураций через Environment Manager
        
        Args:
            environment: Окружение
            config_files: Файлы конфигурации
        """
        logger.debug(f"Applying configurations to environment: {environment}")
        
        # Здесь будет интеграция с C20.5 (Environment Manager)
        # Временная заглушка
        for filename, content in config_files.items():
            logger.info(f"Applying {filename} to {environment}")
    
    async def _log_rollback_success(self, rollback_id: str, 
                                  target_deployment: DeploymentResponse,
                                  target_version: str):
        """
        Логирование успешного отката в Alert Manager (BR18)
        
        Args:
            rollback_id: ID отката
            target_deployment: Целевой деплой
            target_version: Целевая версия
        """
        logger.debug(f"Logging rollback success: {rollback_id}")
        
        # Здесь будет интеграция с BR18 (Alert Manager)
        # Временная заглушка
        pass
    
    async def _log_rollback_failure(self, rollback_id: str, error_message: str):
        """
        Логирование ошибки отката в Alert Manager (BR18)
        
        Args:
            rollback_id: ID отката
            error_message: Сообщение об ошибке
        """
        logger.debug(f"Logging rollback failure: {rollback_id}")
        
        # Здесь будет интеграция с BR18 (Alert Manager)
        # Временная заглушка
        pass
    
    async def handle_alert_notification(self, alert: AlertNotification) -> Optional[str]:
        """
        Обработка уведомления от Alert Manager (BR18)
        
        Args:
            alert: Уведомление об алерте
            
        Returns:
            ID инициированного отката или None если откат не требуется
        """
        logger.info(f"Handling alert notification: {alert.alert_id}")
        
        # Проверяем, требуется ли откат
        if alert.severity != "critical":
            logger.debug(f"Alert severity is not critical: {alert.severity}")
            return None
        
        # Определяем деплой для отката
        deploy_id = alert.deploy_id
        environment = alert.environment
        
        if not deploy_id and not environment:
            logger.warning(f"Alert {alert.alert_id} has no deploy_id or environment")
            return None
        
        # Создаем запрос на откат
        rollback_request = RollbackRequest(
            deploy_id=deploy_id,
            environment=environment,
            reason=f"Automatic rollback triggered by alert: {alert.alert_id}",
            target_version=None  # Автоматический выбор предыдущей версии
        )
        
        try:
            # Выполняем откат
            rollback_response = await self.execute_rollback(rollback_request)
            return rollback_response.rollback_id
        except Exception as e:
            logger.error(f"Failed to execute automatic rollback: {str(e)}")
            return None
    
    def get_rollback_history(self, limit: int = 100, offset: int = 0) -> List:
        """
        Получение истории откатов
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение
            
        Returns:
            Список откатов
        """
        logger.debug(f"Getting rollback history (limit={limit}, offset={offset})")
        return self.repository.get_rollbacks(limit, offset)
    
    def get_rollback_by_id(self, rollback_id: str) -> Optional:
        """
        Получение информации об откате по ID
        
        Args:
            rollback_id: ID отката
            
        Returns:
            Информация об откате или None если не найден
        """
        logger.debug(f"Getting rollback: {rollback_id}")
        return self.repository.get_rollback_by_id(rollback_id)
    
    def health_check(self) -> HealthResponse:
        """
        Проверка здоровья сервиса
        
        Returns:
            Информация о здоровье сервиса
        """
        db_healthy = self.repository.health_check()
        deployment_count = self.repository.get_deployment_count()
        rollback_count = self.repository.get_rollback_count()
        
        return HealthResponse(
            status="ok" if db_healthy else "degraded",
            deployment_count=deployment_count,
            rollback_count=rollback_count,
            database_status="healthy" if db_healthy else "unhealthy",
            timestamp=datetime.now()
        )