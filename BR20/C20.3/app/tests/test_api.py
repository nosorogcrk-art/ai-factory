import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.main import app
from app.models.deployment import (
    DeploymentCreate, DeploymentResponse, RollbackRequest, RollbackResponse,
    RollbackStatus, AlertNotification, HealthResponse, DeploymentStatus
)
from app.services.rollback_service import RollbackService


class TestRollbackAPI:
    """Тесты для API Rollback Manager"""
    
    @pytest.fixture
    def client(self):
        """Создание тестового клиента"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_deployment_data(self):
        """Пример данных для создания деплоя"""
        return {
            "deploy_id": "dep_123",
            "repository": "ai-factory",
            "commit_hash": "abc123",
            "tag": "v1.0.0",
            "environment": "production",
            "config_files": ["docker-compose.yml", "config.env"],
            "description": "Initial deployment"
        }
    
    @pytest.fixture
    def mock_deployment_response(self):
        """Мок ответа деплоя"""
        return DeploymentResponse(
            id=1,
            deploy_id="dep_123",
            repository="ai-factory",
            commit_hash="abc123",
            tag="v1.0.0",
            environment="production",
            config_files=["docker-compose.yml", "config.env"],
            description="Initial deployment",
            status=DeploymentStatus.SUCCESS,
            created_at=datetime.now()
        )
    
    @pytest.fixture
    def mock_rollback_response(self):
        """Мок ответа отката"""
        return RollbackResponse(
            rollback_id="rb_abc123",
            status=RollbackStatus.IN_PROGRESS,
            message="Rollback initiated",
            deploy_id="dep_123",
            target_version="v1.0.0",
            created_at=datetime.now()
        )
    
    def test_health_check(self, client):
        """Тест healthcheck эндпоинта"""
        # Act
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["ok", "degraded"]
        assert "deployment_count" in data
        assert "rollback_count" in data
        assert "database_status" in data
        assert "timestamp" in data
    
    def test_record_deployment_success(self, client, sample_deployment_data, mock_deployment_response):
        """Тест успешной записи деплоя через API"""
        # Arrange
        with patch.object(RollbackService, 'record_deployment', AsyncMock(return_value=mock_deployment_response)):
            # Act
            response = client.post("/deployments", json=sample_deployment_data)
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["deploy_id"] == "dep_123"
            assert data["repository"] == "ai-factory"
            assert data["environment"] == "production"
    
    def test_record_deployment_duplicate_id(self, client, sample_deployment_data):
        """Тест записи деплоя с дублирующим ID через API"""
        # Arrange
        with patch.object(RollbackService, 'record_deployment', 
                         AsyncMock(side_effect=ValueError("Deploy ID dep_123 already exists"))):
            # Act
            response = client.post("/deployments", json=sample_deployment_data)
            
            # Assert
            assert response.status_code == 409
            data = response.json()
            assert "detail" in data
            assert "dep_123 already exists" in data["detail"]
    
    def test_get_deployments(self, client, mock_deployment_response):
        """Тест получения списка деплоев через API"""
        # Arrange
        mock_deployments = [mock_deployment_response]
        
        with patch.object(RollbackService, 'get_deployments', return_value=mock_deployments):
            # Act
            response = client.get("/deployments")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["deploy_id"] == "dep_123"
    
    def test_get_deployments_with_filters(self, client, mock_deployment_response):
        """Тест получения деплоев с фильтрами через API"""
        # Arrange
        mock_deployments = [mock_deployment_response]
        
        with patch.object(RollbackService, 'get_deployments', return_value=mock_deployments):
            # Act
            response = client.get("/deployments?limit=10&offset=0&environment=production")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
    
    def test_get_deployment_by_id_success(self, client, mock_deployment_response):
        """Тест получения деплоя по ID через API"""
        # Arrange
        with patch.object(RollbackService, 'get_deployment_by_id', return_value=mock_deployment_response):
            # Act
            response = client.get("/deployments/dep_123")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["deploy_id"] == "dep_123"
            assert data["repository"] == "ai-factory"
    
    def test_get_deployment_by_id_not_found(self, client):
        """Тест получения несуществующего деплоя по ID через API"""
        # Arrange
        with patch.object(RollbackService, 'get_deployment_by_id', return_value=None):
            # Act
            response = client.get("/deployments/nonexistent")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найден" in data["detail"]
    
    def test_get_latest_deployment_success(self, client, mock_deployment_response):
        """Тест получения последнего деплоя через API"""
        # Arrange
        with patch.object(RollbackService, 'get_latest_deployment', return_value=mock_deployment_response):
            # Act
            response = client.get("/deployments/latest")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["deploy_id"] == "dep_123"
    
    def test_get_latest_deployment_not_found(self, client):
        """Тест получения последнего деплоя когда нет деплоев"""
        # Arrange
        with patch.object(RollbackService, 'get_latest_deployment', return_value=None):
            # Act
            response = client.get("/deployments/latest")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "Деплои не найдены" in data["detail"]
    
    def test_get_latest_deployment_with_environment(self, client, mock_deployment_response):
        """Тест получения последнего деплоя с фильтром по окружению"""
        # Arrange
        with patch.object(RollbackService, 'get_latest_deployment', return_value=mock_deployment_response):
            # Act
            response = client.get("/deployments/latest?environment=production")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["deploy_id"] == "dep_123"
    
    def test_execute_rollback_success(self, client, mock_rollback_response):
        """Тест успешного выполнения отката через API"""
        # Arrange
        rollback_request = {
            "deploy_id": "dep_123",
            "reason": "Test rollback",
            "target_version": "v1.0.0"
        }
        
        with patch.object(RollbackService, 'execute_rollback', AsyncMock(return_value=mock_rollback_response)):
            # Act
            response = client.post("/rollback", json=rollback_request)
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["rollback_id"] == "rb_abc123"
            assert data["status"] == "in_progress"
            assert data["message"] == "Rollback initiated"
    
    def test_execute_rollback_bad_request(self, client):
        """Тест выполнения отката с невалидными данными"""
        # Arrange
        rollback_request = {
            "reason": "Test rollback"
        }
        
        with patch.object(RollbackService, 'execute_rollback', 
                         AsyncMock(side_effect=ValueError("Either deploy_id or environment must be specified"))):
            # Act
            response = client.post("/rollback", json=rollback_request)
            
            # Assert
            assert response.status_code == 400
            data = response.json()
            assert "detail" in data
            assert "must be specified" in data["detail"]
    
    def test_get_rollback_history(self, client):
        """Тест получения истории откатов через API"""
        # Arrange
        from app.models.deployment import RollbackHistoryResponse, RollbackStatus
        from datetime import datetime
        
        mock_rollback = RollbackHistoryResponse(
            id=1,
            rollback_id="rb_abc123",
            deploy_id="dep_123",
            target_version="v1.0.0",
            reason="Test rollback",
            status=RollbackStatus.COMPLETED,
            created_at=datetime(2024, 1, 1, 0, 0, 0),
            completed_at=datetime(2024, 1, 1, 0, 5, 0)
        )
        
        mock_rollbacks = [mock_rollback]
        
        with patch.object(RollbackService, 'get_rollback_history', return_value=mock_rollbacks):
            # Act
            response = client.get("/rollback/history")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["rollback_id"] == "rb_abc123"
    
    def test_get_rollback_by_id_success(self, client):
        """Тест получения информации об откате по ID через API"""
        # Arrange
        mock_rollback = Mock()
        mock_rollback.dict.return_value = {
            "id": 1,
            "rollback_id": "rb_abc123",
            "deploy_id": "dep_123",
            "target_version": "v1.0.0",
            "reason": "Test rollback",
            "status": "completed",
            "created_at": "2024-01-01T00:00:00",
            "completed_at": "2024-01-01T00:05:00"
        }
        
        with patch.object(RollbackService, 'get_rollback_by_id', return_value=mock_rollback):
            # Act
            response = client.get("/rollback/rb_abc123")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["rollback_id"] == "rb_abc123"
            assert data["deploy_id"] == "dep_123"
    
    def test_get_rollback_by_id_not_found(self, client):
        """Тест получения несуществующего отката по ID через API"""
        # Arrange
        with patch.object(RollbackService, 'get_rollback_by_id', return_value=None):
            # Act
            response = client.get("/rollback/nonexistent")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найден" in data["detail"]
    
    def test_handle_alert_notification_rollback_triggered(self, client):
        """Тест обработки алерта с инициированием отката"""
        # Arrange
        alert_data = {
            "alert_id": "alert_123",
            "severity": "critical",
            "message": "Critical error detected",
            "deploy_id": "dep_123",
            "environment": "production",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        with patch.object(RollbackService, 'handle_alert_notification', 
                         AsyncMock(return_value="rb_abc123")):
            # Act
            response = client.post("/alerts", json=alert_data)
            
            # Assert
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "rollback_triggered"
            assert data["rollback_id"] == "rb_abc123"
            assert "Откат инициирован" in data["message"]
    
    def test_handle_alert_notification_no_action(self, client):
        """Тест обработки алерта без инициирования отката"""
        # Arrange
        alert_data = {
            "alert_id": "alert_123",
            "severity": "warning",
            "message": "Warning detected",
            "deploy_id": "dep_123",
            "environment": "production",
            "timestamp": "2024-01-01T00:00:00"
        }
        
        with patch.object(RollbackService, 'handle_alert_notification', 
                         AsyncMock(return_value=None)):
            # Act
            response = client.post("/alerts", json=alert_data)
            
            # Assert
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "no_action_required"
            assert "Откат не требуется" in data["message"]
    
    def test_internal_server_error(self, client, sample_deployment_data):
        """Тест обработки внутренней ошибки сервера"""
        # Arrange
        with patch.object(RollbackService, 'record_deployment', 
                         AsyncMock(side_effect=Exception("Unexpected error"))):
            # Act
            response = client.post("/deployments", json=sample_deployment_data)
            
            # Assert
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Внутренняя ошибка сервера" in data["detail"]