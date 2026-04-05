import pytest
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.models.deployment import (
    DeploymentCreate, DeploymentResponse, RollbackRequest, RollbackResponse,
    RollbackStatus, AlertNotification
)
from app.services.rollback_service import RollbackService
from app.repositories.deployment_repository import DeploymentRepository


class TestRollbackService:
    """Тесты для RollbackService"""
    
    @pytest.fixture
    def temp_db(self):
        """Создание временной базы данных для тестов"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        yield db_path
        # Удаление временного файла после тестов
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    def repository(self, temp_db):
        """Создание репозитория с временной БД"""
        return DeploymentRepository(db_path=temp_db)
    
    @pytest.fixture
    def service(self, repository):
        """Создание сервиса"""
        return RollbackService(repository=repository)
    
    @pytest.fixture
    def sample_deployment_data(self):
        """Пример данных для создания деплоя"""
        return DeploymentCreate(
            deploy_id="dep_123",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["docker-compose.yml", "config.env"],
            description="Initial deployment"
        )
    
    @pytest.mark.asyncio
    async def test_record_deployment_success(self, service, sample_deployment_data):
        """Тест успешной записи деплоя"""
        # Act
        result = await service.record_deployment(sample_deployment_data)
        
        # Assert
        assert result.deploy_id == "dep_123"
        assert result.repository == "ai-factory"
        assert result.commit_hash == "abc123"
        assert result.tag == "v1.0.0"
        assert result.environment == "production"
        assert result.config_files == ["docker-compose.yml", "config.env"]
        assert result.description == "Initial deployment"
    
    @pytest.mark.asyncio
    async def test_record_deployment_duplicate_id(self, service, sample_deployment_data):
        """Тест записи деплоя с дублирующим ID"""
        # Arrange
        await service.record_deployment(sample_deployment_data)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Deploy ID dep_123 already exists"):
            await service.record_deployment(sample_deployment_data)
    
    def test_get_deployments(self, service, sample_deployment_data):
        """Тест получения списка деплоев"""
        # Arrange
        import asyncio
        asyncio.run(service.record_deployment(sample_deployment_data))
        
        # Act
        deployments = service.get_deployments()
        
        # Assert
        assert len(deployments) == 1
        assert deployments[0].deploy_id == "dep_123"
    
    def test_get_deployment_by_id_existing(self, service, sample_deployment_data):
        """Тест получения существующего деплоя по ID"""
        # Arrange
        import asyncio
        asyncio.run(service.record_deployment(sample_deployment_data))
        
        # Act
        deployment = service.get_deployment_by_id("dep_123")
        
        # Assert
        assert deployment is not None
        assert deployment.deploy_id == "dep_123"
    
    def test_get_deployment_by_id_nonexistent(self, service):
        """Тест получения несуществующего деплоя по ID"""
        # Act
        deployment = service.get_deployment_by_id("nonexistent")
        
        # Assert
        assert deployment is None
    
    def test_get_latest_deployment(self, service):
        """Тест получения последнего деплоя"""
        # Arrange
        import asyncio
        import time
        
        deployment1 = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        # Добавляем небольшую задержку между созданиями деплоев
        asyncio.run(service.record_deployment(deployment1))
        time.sleep(0.1)
        
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        asyncio.run(service.record_deployment(deployment2))
        
        # Act
        latest = service.get_latest_deployment("production")
        
        # Assert
        assert latest is not None
        assert latest.deploy_id == "dep_2"
    
    @pytest.mark.asyncio
    async def test_execute_rollback_with_deploy_id(self, service):
        """Тест выполнения отката с указанием deploy_id"""
        # Arrange
        deployment1 = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        await service.record_deployment(deployment1)
        await service.record_deployment(deployment2)
        
        rollback_request = RollbackRequest(
            deploy_id="dep_2",
            reason="Test rollback",
            target_version="v1.0.0"
        )
        
        # Act
        with patch.object(service, '_perform_rollback_async', AsyncMock()):
            result = await service.execute_rollback(rollback_request)
        
        # Assert
        assert result.rollback_id is not None
        assert result.status == RollbackStatus.IN_PROGRESS
        assert result.deploy_id == "dep_2"
        assert result.target_version == "v1.0.0"
        assert "Rollback initiated" in result.message
    
    @pytest.mark.asyncio
    async def test_execute_rollback_with_environment(self, service):
        """Тест выполнения отката с указанием окружения"""
        # Arrange
        deployment = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        await service.record_deployment(deployment)
        
        rollback_request = RollbackRequest(
            environment="production",
            reason="Test rollback",
            target_version="v0.9.0"
        )
        
        # Act
        with patch.object(service, '_perform_rollback_async', AsyncMock()):
            result = await service.execute_rollback(rollback_request)
        
        # Assert
        assert result.rollback_id is not None
        assert result.status == RollbackStatus.IN_PROGRESS
        assert result.deploy_id == "dep_1"
        assert result.target_version == "v0.9.0"
    
    @pytest.mark.asyncio
    async def test_execute_rollback_without_target_version(self, service):
        """Тест выполнения отката без указания целевой версии"""
        # Arrange
        import time
        
        deployment1 = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        await service.record_deployment(deployment1)
        time.sleep(0.1)  # Добавляем задержку
        
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        await service.record_deployment(deployment2)
        
        rollback_request = RollbackRequest(
            deploy_id="dep_2",
            reason="Test rollback"
        )
        
        # Act
        with patch.object(service, '_perform_rollback_async', AsyncMock()):
            result = await service.execute_rollback(rollback_request)
        
        # Assert
        assert result.rollback_id is not None
        assert result.status == RollbackStatus.IN_PROGRESS
        assert result.deploy_id == "dep_2"
        assert result.target_version == "v1.0.0"  # Автоматически выбрана предыдущая версия
    
    @pytest.mark.asyncio
    async def test_execute_rollback_deployment_not_found(self, service):
        """Тест выполнения отката с несуществующим деплоем"""
        # Arrange
        rollback_request = RollbackRequest(
            deploy_id="nonexistent",
            reason="Test rollback",
            target_version="v1.0.0"
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="Deployment not found: nonexistent"):
            await service.execute_rollback(rollback_request)
    
    @pytest.mark.asyncio
    async def test_execute_rollback_missing_parameters(self, service):
        """Тест выполнения отката без указания параметров"""
        # Arrange
        rollback_request = RollbackRequest(
            reason="Test rollback"
        )
        
        # Act & Assert
        with pytest.raises(ValueError, match="Either deploy_id or environment must be specified"):
            await service.execute_rollback(rollback_request)
    
    @pytest.mark.asyncio
    async def test_handle_alert_notification_critical(self, service):
        """Тест обработки критического алерта"""
        # Arrange
        import time
        
        deployment1 = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        await service.record_deployment(deployment1)
        time.sleep(0.1)
        
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        await service.record_deployment(deployment2)
        
        alert = AlertNotification(
            alert_id="alert_123",
            severity="critical",
            message="Critical error detected",
            deploy_id="dep_2",
            environment="production",
            timestamp=datetime.now()
        )
        
        # Act
        with patch.object(service, '_perform_rollback_async', AsyncMock()):
            rollback_id = await service.handle_alert_notification(alert)
        
        # Assert
        assert rollback_id is not None
        assert rollback_id.startswith("rb_")
    
    @pytest.mark.asyncio
    async def test_handle_alert_notification_warning(self, service):
        """Тест обработки некритического алерта"""
        # Arrange
        alert = AlertNotification(
            alert_id="alert_123",
            severity="warning",
            message="Warning detected",
            deploy_id="dep_1",
            environment="production",
            timestamp=datetime.now()
        )
        
        # Act
        rollback_id = await service.handle_alert_notification(alert)
        
        # Assert
        assert rollback_id is None
    
    @pytest.mark.asyncio
    async def test_handle_alert_notification_no_deploy_info(self, service):
        """Тест обработки алерта без информации о деплое"""
        # Arrange
        alert = AlertNotification(
            alert_id="alert_123",
            severity="critical",
            message="Critical error detected",
            timestamp=datetime.now()
        )
        
        # Act
        rollback_id = await service.handle_alert_notification(alert)
        
        # Assert
        assert rollback_id is None
    
    def test_get_rollback_history(self, service):
        """Тест получения истории откатов"""
        # Arrange
        import asyncio
        
        deployment = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        asyncio.run(service.record_deployment(deployment))
        
        # Создание отката через репозиторий напрямую
        rollback_id = service.repository.create_rollback(
            deploy_id="dep_1",
            target_version="v0.9.0",
            reason="Test rollback"
        )
        
        # Act
        rollbacks = service.get_rollback_history()
        
        # Assert
        assert len(rollbacks) == 1
        assert rollbacks[0].rollback_id == rollback_id
    
    def test_get_rollback_by_id(self, service):
        """Тест получения информации об откате по ID"""
        # Arrange
        import asyncio
        
        deployment = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["file1.yml"]
        )
        
        asyncio.run(service.record_deployment(deployment))
        
        rollback_id = service.repository.create_rollback(
            deploy_id="dep_1",
            target_version="v0.9.0",
            reason="Test rollback"
        )
        
        # Act
        rollback = service.get_rollback_by_id(rollback_id)
        
        # Assert
        assert rollback is not None
        assert rollback.rollback_id == rollback_id
        assert rollback.deploy_id == "dep_1"
        assert rollback.target_version == "v0.9.0"
    
    def test_health_check_healthy(self, service, sample_deployment_data):
        """Тест проверки здоровья при рабочей БД"""
        # Arrange
        import asyncio
        asyncio.run(service.record_deployment(sample_deployment_data))
        
        # Act
        health = service.health_check()
        
        # Assert
        assert health.status == "ok"
        assert health.deployment_count == 1
        assert health.rollback_count == 0
        assert health.database_status == "healthy"
        assert health.timestamp is not None
    
    def test_health_check_with_mocked_repository(self):
        """Тест проверки здоровья с моком репозитория"""
        # Arrange
        mock_repository = Mock()
        mock_repository.health_check.return_value = False
        mock_repository.get_deployment_count.return_value = 5
        mock_repository.get_rollback_count.return_value = 2
        
        service = RollbackService(repository=mock_repository)
        
        # Act
        health = service.health_check()
        
        # Assert
        assert health.status == "degraded"
        assert health.deployment_count == 5
        assert health.rollback_count == 2
        assert health.database_status == "unhealthy"
        mock_repository.health_check.assert_called_once()
        mock_repository.get_deployment_count.assert_called_once()
        mock_repository.get_rollback_count.assert_called_once()