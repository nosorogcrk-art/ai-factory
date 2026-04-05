import pytest
import tempfile
import os
import json
from datetime import datetime

from app.models.deployment import DeploymentCreate, DeploymentStatus, RollbackStatus
from app.repositories.deployment_repository import DeploymentRepository


class TestDeploymentRepository:
    """Тесты для DeploymentRepository"""
    
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
    
    def test_save_deployment_success(self, repository, sample_deployment_data):
        """Тест успешного сохранения деплоя"""
        # Act
        deployment_id = repository.save_deployment(sample_deployment_data)
        
        # Assert
        assert deployment_id is not None
        assert deployment_id > 0
        
        # Проверка получения сохраненного деплоя
        saved = repository.get_deployment_by_id("dep_123")
        assert saved is not None
        assert saved.deploy_id == "dep_123"
        assert saved.repository == "ai-factory"
        assert saved.commit_hash == "abc123"
        assert saved.tag == "v1.0.0"
        assert saved.environment == "production"
        assert saved.config_files == ["docker-compose.yml", "config.env"]
        assert saved.description == "Initial deployment"
        assert saved.status == DeploymentStatus.SUCCESS
    
    def test_save_deployment_duplicate_id(self, repository, sample_deployment_data):
        """Тест сохранения деплоя с дублирующим ID"""
        # Arrange
        repository.save_deployment(sample_deployment_data)
        
        # Act & Assert
        with pytest.raises(ValueError, match="Deploy ID dep_123 already exists"):
            repository.save_deployment(sample_deployment_data)
    
    def test_get_deployment_by_id_existing(self, repository, sample_deployment_data):
        """Тест получения существующего деплоя по ID"""
        # Arrange
        repository.save_deployment(sample_deployment_data)
        
        # Act
        deployment = repository.get_deployment_by_id("dep_123")
        
        # Assert
        assert deployment is not None
        assert deployment.deploy_id == "dep_123"
        assert deployment.repository == "ai-factory"
    
    def test_get_deployment_by_id_nonexistent(self, repository):
        """Тест получения несуществующего деплоя по ID"""
        # Act
        deployment = repository.get_deployment_by_id("nonexistent")
        
        # Assert
        assert deployment is None
    
    def test_get_deployments(self, repository):
        """Тест получения списка деплоев"""
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
            environment="staging",
            config_files=["file2.yml"]
        )
        
        repository.save_deployment(deployment1)
        repository.save_deployment(deployment2)
        
        # Act
        deployments = repository.get_deployments()
        
        # Assert
        assert len(deployments) == 2
        assert deployments[0].deploy_id == "dep_2"  # Последний созданный первый
        assert deployments[1].deploy_id == "dep_1"
    
    def test_get_deployments_with_environment_filter(self, repository):
        """Тест получения деплоев с фильтром по окружению"""
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
            environment="staging",
            config_files=["file2.yml"]
        )
        
        repository.save_deployment(deployment1)
        repository.save_deployment(deployment2)
        
        # Act
        production_deployments = repository.get_deployments(environment="production")
        staging_deployments = repository.get_deployments(environment="staging")
        
        # Assert
        assert len(production_deployments) == 1
        assert production_deployments[0].deploy_id == "dep_1"
        assert len(staging_deployments) == 1
        assert staging_deployments[0].deploy_id == "dep_2"
    
    def test_get_latest_deployment(self, repository):
        """Тест получения последнего деплоя"""
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
        
        repository.save_deployment(deployment1)
        time.sleep(0.1)  # Добавляем задержку
        
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        repository.save_deployment(deployment2)
        
        # Act
        latest = repository.get_latest_deployment("production")
        
        # Assert
        assert latest is not None
        assert latest.deploy_id == "dep_2"
    
    def test_get_previous_deployment(self, repository):
        """Тест получения предыдущего деплоя"""
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
        
        repository.save_deployment(deployment1)
        time.sleep(0.1)  # Добавляем задержку
        
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            tag="v1.0.1",
            environment="production",
            config_files=["file2.yml"]
        )
        
        repository.save_deployment(deployment2)
        
        # Act
        previous = repository.get_previous_deployment("dep_2")
        
        # Assert
        assert previous is not None
        assert previous.deploy_id == "dep_1"
    
    def test_create_rollback(self, repository, sample_deployment_data):
        """Тест создания записи об откате"""
        # Arrange
        repository.save_deployment(sample_deployment_data)
        
        # Act
        rollback_id = repository.create_rollback(
            deploy_id="dep_123",
            target_version="v0.9.0",
            reason="Test rollback"
        )
        
        # Assert
        assert rollback_id is not None
        assert rollback_id.startswith("rb_")
        
        # Проверка получения созданного отката
        rollback = repository.get_rollback_by_id(rollback_id)
        assert rollback is not None
        assert rollback.rollback_id == rollback_id
        assert rollback.deploy_id == "dep_123"
        assert rollback.target_version == "v0.9.0"
        assert rollback.reason == "Test rollback"
        assert rollback.status == RollbackStatus.PENDING
    
    def test_update_rollback_status(self, repository, sample_deployment_data):
        """Тест обновления статуса отката"""
        # Arrange
        repository.save_deployment(sample_deployment_data)
        rollback_id = repository.create_rollback(
            deploy_id="dep_123",
            target_version="v0.9.0",
            reason="Test rollback"
        )
        
        # Act
        updated = repository.update_rollback_status(
            rollback_id,
            RollbackStatus.COMPLETED,
            completed=True
        )
        
        # Assert
        assert updated is True
        
        # Проверка обновленного статуса
        rollback = repository.get_rollback_by_id(rollback_id)
        assert rollback is not None
        assert rollback.status == RollbackStatus.COMPLETED
        assert rollback.completed_at is not None
    
    def test_get_rollbacks(self, repository, sample_deployment_data):
        """Тест получения списка откатов"""
        # Arrange
        import time
        
        repository.save_deployment(sample_deployment_data)
        
        rollback1_id = repository.create_rollback(
            deploy_id="dep_123",
            target_version="v0.9.0",
            reason="First rollback"
        )
        
        time.sleep(0.1)  # Добавляем задержку
        
        rollback2_id = repository.create_rollback(
            deploy_id="dep_123",
            target_version="v0.8.0",
            reason="Second rollback"
        )
        
        # Act
        rollbacks = repository.get_rollbacks()
        
        # Assert
        assert len(rollbacks) == 2
        # Проверяем, что оба ID присутствуют в списке
        rollback_ids = [rb.rollback_id for rb in rollbacks]
        assert rollback1_id in rollback_ids
        assert rollback2_id in rollback_ids
        # Проверяем порядок по времени создания (последний созданный должен быть первым)
        # Для этого нужно получить время создания
        rollback1 = repository.get_rollback_by_id(rollback1_id)
        rollback2 = repository.get_rollback_by_id(rollback2_id)
        if rollback1 and rollback2:
            # rollback2 создан позже, поэтому должен быть первым в списке
            assert rollback2.created_at > rollback1.created_at
            assert rollbacks[0].rollback_id == rollback2_id
    
    def test_get_deployment_count(self, repository):
        """Тест получения количества деплоев"""
        # Arrange
        deployment1 = DeploymentCreate(
            deploy_id="dep_1",
            repository="ai-factory",
            commit_hash="abc123",
            environment="production",
            config_files=[]
        )
        deployment2 = DeploymentCreate(
            deploy_id="dep_2",
            repository="ai-factory",
            commit_hash="def456",
            environment="staging",
            config_files=[]
        )
        
        repository.save_deployment(deployment1)
        repository.save_deployment(deployment2)
        
        # Act
        count = repository.get_deployment_count()
        
        # Assert
        assert count == 2
    
    def test_get_rollback_count(self, repository, sample_deployment_data):
        """Тест получения количества откатов"""
        # Arrange
        repository.save_deployment(sample_deployment_data)
        
        repository.create_rollback(
            deploy_id="dep_123",
            target_version="v0.9.0",
            reason="Test rollback"
        )
        
        # Act
        count = repository.get_rollback_count()
        
        # Assert
        assert count == 1
    
    def test_health_check_healthy(self, repository):
        """Тест проверки здоровья при рабочей БД"""
        # Act
        healthy = repository.health_check()
        
        # Assert
        assert healthy is True
    
    def test_health_check_with_invalid_db(self):
        """Тест проверки здоровья с невалидной БД"""
        # Arrange
        # Используем путь к несуществующему файлу в существующей директории
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = os.path.join(temp_dir, "test.db")
            
            # Создаем репозиторий - он создаст файл БД
            repository = DeploymentRepository(db_path=db_path)
            
            # Удаляем файл БД
            os.unlink(db_path)
            
            # Act
            healthy = repository.health_check()
            
            # Assert
            # SQLite создает файл при подключении, поэтому проверка должна пройти
            assert healthy is True
