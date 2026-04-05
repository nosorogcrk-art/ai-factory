import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.main import app
from app.models.config import ConfigContentResponse, ConfigResponse, ConfigDiffResponse
from app.services.config_service import ConfigService


class TestConfigAPI:
    """Тесты для API конфигураций"""
    
    @pytest.fixture
    def client(self):
        """Создание тестового клиента"""
        return TestClient(app)
    
    @pytest.fixture
    def sample_config_data(self):
        """Пример данных для создания конфигурации"""
        return {
            "content": "version: '3.8'\nservices:\n  app:\n    image: nginx:latest",
            "version": "v1.0.0",
            "description": "Initial docker-compose config",
            "config_type": "docker-compose"
        }
    
    @pytest.fixture
    def mock_config_response(self):
        """Мок ответа конфигурации"""
        return ConfigContentResponse(
            id=1,
            version="v1.0.0",
            config_type="docker-compose",
            description="Initial docker-compose config",
            content="version: '3.8'\nservices:\n  app:\n    image: nginx:latest",
            created_at="2024-01-01T00:00:00",
            hash="abc123",
            size_bytes=100
        )
    
    def test_health_check(self, client):
        """Тест healthcheck эндпоинта"""
        # Act
        response = client.get("/health")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version_count" in data
        assert "database_status" in data
        assert "timestamp" in data
    
    def test_create_config_success(self, client, sample_config_data, mock_config_response):
        """Тест успешного создания конфигурации через API"""
        # Arrange
        with patch.object(ConfigService, 'create_config', return_value=mock_config_response):
            # Act
            response = client.post("/configs", json=sample_config_data)
            
            # Assert
            assert response.status_code == 201
            data = response.json()
            assert data["version"] == "v1.0.0"
            assert data["config_type"] == "docker-compose"
            assert "nginx:latest" in data["content"]
    
    def test_create_config_duplicate_version(self, client, sample_config_data):
        """Тест создания конфигурации с дублирующей версией через API"""
        # Arrange
        with patch.object(ConfigService, 'create_config', side_effect=ValueError("Версия v1.0.0 уже существует")):
            # Act
            response = client.post("/configs", json=sample_config_data)
            
            # Assert
            assert response.status_code == 409
            data = response.json()
            assert "detail" in data
            assert "v1.0.0 уже существует" in data["detail"]
    
    def test_get_all_configs(self, client):
        """Тест получения списка всех конфигураций через API"""
        # Arrange
        mock_configs = [
            ConfigResponse(
                id=1,
                version="v1.0.0",
                config_type="docker-compose",
                description="Initial",
                created_at="2024-01-01T00:00:00",
                hash="abc123",
                size_bytes=100
            ),
            ConfigResponse(
                id=2,
                version="v1.0.1",
                config_type="docker-compose",
                description="Updated",
                created_at="2024-01-02T00:00:00",
                hash="def456",
                size_bytes=150
            )
        ]
        
        with patch.object(ConfigService, 'get_all_configs', return_value=mock_configs):
            # Act
            response = client.get("/configs")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["version"] == "v1.0.0"
            assert data[1]["version"] == "v1.0.1"
    
    def test_get_all_configs_with_pagination(self, client):
        """Тест получения конфигураций с пагинацией через API"""
        # Arrange
        mock_configs = [
            ConfigResponse(
                id=1,
                version="v1.0.0",
                config_type="docker-compose",
                description="Initial",
                created_at="2024-01-01T00:00:00",
                hash="abc123",
                size_bytes=100
            )
        ]
        
        with patch.object(ConfigService, 'get_all_configs', return_value=mock_configs):
            # Act
            response = client.get("/configs?limit=10&offset=0")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
    
    def test_get_config_versions(self, client):
        """Тест получения списка версий через API"""
        # Arrange
        mock_versions = ["v1.0.0", "v1.0.1", "v1.0.2"]
        
        with patch.object(ConfigService, 'get_config_versions', return_value=mock_versions):
            # Act
            response = client.get("/configs/versions")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            assert "v1.0.0" in data
            assert "v1.0.1" in data
            assert "v1.0.2" in data
    
    def test_get_latest_config_success(self, client, mock_config_response):
        """Тест получения последней конфигурации через API"""
        # Arrange
        with patch.object(ConfigService, 'get_latest_config', return_value=mock_config_response):
            # Act
            response = client.get("/configs/latest")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v1.0.0"
            assert "nginx:latest" in data["content"]
    
    def test_get_latest_config_not_found(self, client):
        """Тест получения последней конфигурации когда нет конфигураций"""
        # Arrange
        with patch.object(ConfigService, 'get_latest_config', return_value=None):
            # Act
            response = client.get("/configs/latest")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "Конфигурации не найдены" in data["detail"]
    
    def test_get_config_by_version_success(self, client, mock_config_response):
        """Тест получения конфигурации по версии через API"""
        # Arrange
        with patch.object(ConfigService, 'get_config', return_value=mock_config_response):
            # Act
            response = client.get("/configs/v1.0.0")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v1.0.0"
            assert "nginx:latest" in data["content"]
    
    def test_get_config_by_version_not_found(self, client):
        """Тест получения несуществующей конфигурации по версии через API"""
        # Arrange
        with patch.object(ConfigService, 'get_config', return_value=None):
            # Act
            response = client.get("/configs/nonexistent")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найдена" in data["detail"]
    
    def test_delete_config_success(self, client):
        """Тест успешного удаления конфигурации через API"""
        # Arrange
        with patch.object(ConfigService, 'delete_config', return_value=True):
            # Act
            response = client.delete("/configs/v1.0.0")
            
            # Assert
            assert response.status_code == 204
    
    def test_delete_config_not_found(self, client):
        """Тест удаления несуществующей конфигурации через API"""
        # Arrange
        with patch.object(ConfigService, 'delete_config', return_value=False):
            # Act
            response = client.delete("/configs/nonexistent")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найдена" in data["detail"]
    
    def test_get_config_diff_success(self, client):
        """Тест получения разницы между версиями через API"""
        # Arrange
        mock_diff = ConfigDiffResponse(
            from_version="v1.0.0",
            to_version="v1.0.1",
            diff="--- a/v1.0.0\n+++ b/v1.0.1\n@@ -1,3 +1,4 @@\n line1\n-line2\n+line2_modified\n line3\n+line4",
            changes_count=3
        )
        
        with patch.object(ConfigService, 'get_diff', return_value=mock_diff):
            # Act
            response = client.get("/configs/diff?from_version=v1.0.0&to_version=v1.0.1")
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["from_version"] == "v1.0.0"
            assert data["to_version"] == "v1.0.1"
            # Проверяем что diff содержит хотя бы одну из строк diff формата
            assert "---" in data["diff"] or "@@" in data["diff"] or "+++" in data["diff"]
            assert data["changes_count"] == 3
    
    def test_get_config_diff_not_found(self, client):
        """Тест получения разницы с несуществующей версией через API"""
        # Arrange
        with patch.object(ConfigService, 'get_diff', return_value=None):
            # Act
            response = client.get("/configs/diff?from_version=v1.0.0&to_version=nonexistent")
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найдены" in data["detail"]
    
    def test_get_config_diff_missing_params(self, client):
        """Тест получения разницы без параметров через API"""
        # Act
        response = client.get("/configs/diff")
        
        # Assert
        assert response.status_code == 422  # Validation error
    
    def test_rollback_to_version_success(self, client, mock_config_response):
        """Тест успешного отката к версии через API"""
        # Arrange
        with patch.object(ConfigService, 'rollback_to_version', return_value=mock_config_response):
            rollback_data = {
                "target_version": "v1.0.0",
                "create_new_version": True
            }
            
            # Act
            response = client.post("/configs/rollback/v1.0.0", json=rollback_data)
            
            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v1.0.0"
    
    def test_rollback_to_version_not_found(self, client):
        """Тест отката к несуществующей версии через API"""
        # Arrange
        with patch.object(ConfigService, 'rollback_to_version', return_value=None):
            rollback_data = {
                "target_version": "nonexistent",
                "create_new_version": True
            }
            
            # Act
            response = client.post("/configs/rollback/nonexistent", json=rollback_data)
            
            # Assert
            assert response.status_code == 404
            data = response.json()
            assert "detail" in data
            assert "не найдена" in data["detail"]
    
    def test_rollback_to_version_without_body(self, client, mock_config_response):
        """Тест отката к версии без тела запроса через API"""
        # Arrange
        with patch.object(ConfigService, 'rollback_to_version', return_value=mock_config_response):
            # Act
            response = client.post("/configs/rollback/v1.0.0", json={})
            
            # Assert
            assert response.status_code == 200  # Использует версию из пути
            data = response.json()
            assert data["version"] == "v1.0.0"
    
    def test_internal_server_error(self, client, sample_config_data):
        """Тест обработки внутренней ошибки сервера"""
        # Arrange
        with patch.object(ConfigService, 'create_config', side_effect=Exception("Unexpected error")):
            # Act
            response = client.post("/configs", json=sample_config_data)
            
            # Assert
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Внутренняя ошибка сервера" in data["detail"]