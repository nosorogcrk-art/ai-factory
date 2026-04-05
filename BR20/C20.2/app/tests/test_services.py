import pytest
import tempfile
import os
from unittest.mock import Mock

from app.models.config import ConfigCreate, RollbackRequest
from app.services.config_service import ConfigService
from app.repositories.config_repository import ConfigRepository


class TestConfigService:
    """Тесты для ConfigService"""
    
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
        return ConfigRepository(db_path=temp_db)
    
    @pytest.fixture
    def service(self, repository):
        """Создание сервиса"""
        return ConfigService(repository)
    
    @pytest.fixture
    def sample_config_data(self):
        """Пример данных для создания конфигурации"""
        return ConfigCreate(
            content="version: '3.8'\nservices:\n  app:\n    image: nginx:latest",
            version="v1.0.0",
            description="Initial docker-compose config",
            config_type="docker-compose"
        )
    
    def test_create_config_success(self, service, sample_config_data):
        """Тест успешного создания конфигурации"""
        # Act
        result = service.create_config(sample_config_data)
        
        # Assert
        assert result.version == "v1.0.0"
        assert result.config_type == "docker-compose"
        assert result.description == "Initial docker-compose config"
        assert "nginx:latest" in result.content
        assert result.hash is not None
        assert result.size_bytes > 0
        assert result.id is not None
    
    def test_create_config_duplicate_version(self, service, sample_config_data):
        """Тест создания конфигурации с дублирующей версией"""
        # Arrange
        service.create_config(sample_config_data)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Версия v1.0.0 уже существует"):
            service.create_config(sample_config_data)
    
    def test_get_config_existing(self, service, sample_config_data):
        """Тест получения существующей конфигурации"""
        # Arrange
        created = service.create_config(sample_config_data)
        
        # Act
        retrieved = service.get_config("v1.0.0")
        
        # Assert
        assert retrieved is not None
        assert retrieved.version == created.version
        assert retrieved.content == created.content
    
    def test_get_config_nonexistent(self, service):
        """Тест получения несуществующей конфигурации"""
        # Act
        result = service.get_config("nonexistent")
        
        # Assert
        assert result is None
    
    def test_get_all_configs(self, service, sample_config_data):
        """Тест получения списка всех конфигураций"""
        # Arrange
        service.create_config(sample_config_data)
        
        # Создаем вторую конфигурацию
        config_data2 = ConfigCreate(
            content="version: '3.9'\nservices:\n  app:\n    image: nginx:alpine",
            version="v1.0.1",
            description="Updated docker-compose config",
            config_type="docker-compose"
        )
        service.create_config(config_data2)
        
        # Act
        configs = service.get_all_configs()
        
        # Assert
        assert len(configs) == 2
        assert configs[0].version == "v1.0.1"  # Последняя созданная первая
        assert configs[1].version == "v1.0.0"
    
    def test_get_config_versions(self, service, sample_config_data):
        """Тест получения списка версий"""
        # Arrange
        service.create_config(sample_config_data)
        
        config_data2 = ConfigCreate(
            content="test",
            version="v1.0.1",
            config_type="docker-compose"
        )
        service.create_config(config_data2)
        
        # Act
        versions = service.get_config_versions()
        
        # Assert
        assert len(versions) == 2
        assert "v1.0.0" in versions
        assert "v1.0.1" in versions
    
    def test_get_latest_config(self, service, sample_config_data):
        """Тест получения последней конфигурации"""
        # Arrange
        service.create_config(sample_config_data)
        
        config_data2 = ConfigCreate(
            content="updated",
            version="v1.0.1",
            config_type="docker-compose"
        )
        service.create_config(config_data2)
        
        # Act
        latest = service.get_latest_config()
        
        # Assert
        assert latest is not None
        assert latest.version == "v1.0.1"
        assert latest.content == "updated"
    
    def test_get_latest_config_empty(self, service):
        """Тест получения последней конфигурации при пустой БД"""
        # Act
        result = service.get_latest_config()
        
        # Assert
        assert result is None
    
    def test_delete_config_existing(self, service, sample_config_data):
        """Тест удаления существующей конфигурации"""
        # Arrange
        service.create_config(sample_config_data)
        
        # Act
        deleted = service.delete_config("v1.0.0")
        
        # Assert
        assert deleted is True
        assert service.get_config("v1.0.0") is None
    
    def test_delete_config_nonexistent(self, service):
        """Тест удаления несуществующей конфигурации"""
        # Act
        deleted = service.delete_config("nonexistent")
        
        # Assert
        assert deleted is False
    
    def test_get_diff_success(self, service):
        """Тест получения разницы между версиями"""
        # Arrange
        config1 = ConfigCreate(
            content="line1\nline2\nline3",
            version="v1.0.0",
            config_type="test"
        )
        config2 = ConfigCreate(
            content="line1\nline2_modified\nline3\nline4",
            version="v1.0.1",
            config_type="test"
        )
        
        service.create_config(config1)
        service.create_config(config2)
        
        # Act
        diff = service.get_diff("v1.0.0", "v1.0.1")
        
        # Assert
        assert diff is not None
        assert diff.from_version == "v1.0.0"
        assert diff.to_version == "v1.0.1"
        assert diff.changes_count > 0
        # Проверяем что diff содержит хотя бы одну из строк diff формата
        assert "---" in diff.diff or "@@" in diff.diff or "+++" in diff.diff
        assert "line2" in diff.diff or "line2_modified" in diff.diff
    
    def test_get_diff_nonexistent_version(self, service, sample_config_data):
        """Тест получения разницы с несуществующей версией"""
        # Arrange
        service.create_config(sample_config_data)
        
        # Act
        diff = service.get_diff("v1.0.0", "nonexistent")
        
        # Assert
        assert diff is None
    
    def test_rollback_to_version_with_new_version(self, service):
        """Тест отката с созданием новой версии"""
        # Arrange
        original = ConfigCreate(
            content="original content",
            version="v1.0.0",
            config_type="test"
        )
        service.create_config(original)
        
        current = ConfigCreate(
            content="current content",
            version="v1.0.1",
            config_type="test"
        )
        service.create_config(current)
        
        rollback_request = RollbackRequest(
            target_version="v1.0.0",
            create_new_version=True
        )
        
        # Act
        result = service.rollback_to_version(rollback_request)
        
        # Assert
        assert result is not None
        assert "v1.0.0-rollback-" in result.version
        assert result.content == "original content"
        assert "Откат к версии v1.0.0" in result.description
    
    def test_rollback_to_version_without_new_version(self, service):
        """Тест отката без создания новой версии"""
        # Arrange
        original = ConfigCreate(
            content="original content",
            version="v1.0.0",
            config_type="test"
        )
        service.create_config(original)
        
        rollback_request = RollbackRequest(
            target_version="v1.0.0",
            create_new_version=False
        )
        
        # Act
        result = service.rollback_to_version(rollback_request)
        
        # Assert
        assert result is not None
        assert result.version == "v1.0.0"
        assert result.content == "original content"
    
    def test_rollback_to_nonexistent_version(self, service):
        """Тест отката к несуществующей версии"""
        # Arrange
        rollback_request = RollbackRequest(
            target_version="nonexistent",
            create_new_version=True
        )
        
        # Act
        result = service.rollback_to_version(rollback_request)
        
        # Assert
        assert result is None
    
    def test_health_check_healthy(self, service, sample_config_data):
        """Тест проверки здоровья при рабочей БД"""
        # Arrange
        service.create_config(sample_config_data)
        
        # Act
        health = service.health_check()
        
        # Assert
        assert health["database_status"] == "healthy"
        assert health["version_count"] == 1
        assert "timestamp" in health
    
    def test_health_check_with_mocked_repository(self):
        """Тест проверки здоровья с моком репозитория"""
        # Arrange
        mock_repository = Mock()
        mock_repository.health_check.return_value = False
        mock_repository.get_count.return_value = 5
        
        service = ConfigService(mock_repository)
        
        # Act
        health = service.health_check()
        
        # Assert
        assert health["database_status"] == "unhealthy"
        assert health["version_count"] == 5
        mock_repository.health_check.assert_called_once()
        mock_repository.get_count.assert_called_once()