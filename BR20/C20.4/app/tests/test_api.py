"""
Интеграционные тесты для API C20.4 Test Runner
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app
from app.models.config import TestRequest, TestType, TestStatus, TestResponse, TestResultsResponse
from app.services.test_service import TestService
from app.repositories.test_repository import TestRepository


class TestAPI:
    """Тесты для API эндпоинтов"""
    
    @pytest.fixture
    def client(self):
        """Фикстура для создания тестового клиента"""
        return TestClient(app)
    
    @pytest.fixture
    def test_request(self):
        """Фикстура для создания тестового запроса"""
        return TestRequest(
            repo="test-repo",
            commit="abc123",
            tests=[TestType.SYNTAX, TestType.SEMANTIC]
        )
    
    def test_root_endpoint(self, client):
        """Тест корневого эндпоинта"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "C20.4 Test Runner"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
    
    def test_health_check(self, client):
        """Тест эндпоинта проверки здоровья"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "timestamp" in data
        assert data["version"] == "1.0"
        assert data["status"] in ["healthy", "unhealthy"]
    
    @patch("app.main.test_service")
    def test_run_tests_success(self, mock_test_service, client, test_request):
        """Тест успешного запуска тестов"""
        # Мокаем сервис
        mock_response = TestResponse(
            test_id="tst_123456",
            status=TestStatus.PENDING,
            created_at="2024-01-01T00:00:00",
            repo="test-repo",
            commit="abc123",
            tests=[TestType.SYNTAX, TestType.SEMANTIC]
        )
        mock_test_service.run_tests = AsyncMock(return_value=mock_response)
        
        # Отправляем запрос
        response = client.post("/test", json=test_request.dict())
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["test_id"] == "tst_123456"
        assert data["status"] == "pending"
        assert data["repo"] == "test-repo"
        assert data["commit"] == "abc123"
        assert "syntax" in data["tests"]
        assert "semantic" in data["tests"]
    
    @patch("app.main.test_service")
    def test_run_tests_service_error(self, mock_test_service, client, test_request):
        """Тест запуска тестов с ошибкой сервиса"""
        # Мокаем сервис с ошибкой
        mock_test_service.run_tests = AsyncMock(side_effect=Exception("Service error"))
        
        # Отправляем запрос
        response = client.post("/test", json=test_request.dict())
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "Failed to start tests" in data["detail"]
    
    @patch("app.main.test_service")
    @patch("app.main.test_repository")
    def test_get_test_results_found(self, mock_repository, mock_test_service, client):
        """Тест получения результатов тестов (найдены)"""
        # Мокаем сервис и репозиторий
        test_id = "tst_123456"
        
        # Создаем мок результатов
        mock_results = TestResultsResponse(
            test_id=test_id,
            status=TestStatus.COMPLETED,
            passed=True,
            results={},
            created_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:01:00"
        )
        
        mock_test_service.get_test_results = AsyncMock(return_value=mock_results)
        mock_repository.get_test = MagicMock(return_value=None)
        
        # Отправляем запрос
        response = client.get(f"/results/{test_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["test_id"] == test_id
        assert data["status"] == "completed"
        assert data["passed"] is True
    
    @patch("app.main.test_service")
    @patch("app.main.test_repository")
    def test_get_test_results_not_found(self, mock_repository, mock_test_service, client):
        """Тест получения результатов несуществующего теста"""
        # Мокаем сервис и репозиторий
        test_id = "nonexistent"
        
        mock_test_service.get_test_results = AsyncMock(return_value=None)
        mock_repository.get_test = MagicMock(return_value=None)
        
        # Отправляем запрос
        response = client.get(f"/results/{test_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert test_id in data["detail"]
    
    @patch("app.main.test_repository")
    def test_get_recent_tests_success(self, mock_repository, client):
        """Тест получения списка последних тестов"""
        # Мокаем репозиторий
        mock_tests = [
            TestResultsResponse(
                test_id="tst_123456",
                status=TestStatus.COMPLETED,
                passed=True,
                results={},
                created_at="2024-01-01T00:00:00",
                completed_at="2024-01-01T00:01:00"
            )
        ]
        
        mock_repository.get_recent_tests = MagicMock(return_value=mock_tests)
        
        # Отправляем запрос
        response = client.get("/tests/recent")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["test_id"] == "tst_123456"
    
    @patch("app.main.test_repository")
    def test_get_recent_tests_with_limit(self, mock_repository, client):
        """Тест получения списка последних тестов с указанием лимита"""
        # Мокаем репозиторий
        mock_tests = [
            TestResultsResponse(
                test_id=f"tst_{i}",
                status=TestStatus.COMPLETED,
                passed=True,
                results={},
                created_at="2024-01-01T00:00:00",
                completed_at="2024-01-01T00:01:00"
            )
            for i in range(5)
        ]
        
        mock_repository.get_recent_tests = MagicMock(return_value=mock_tests)
        
        # Отправляем запрос с лимитом
        response = client.get("/tests/recent?limit=5")
        
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) == 5
    
    @patch("app.main.test_repository")
    def test_cancel_test_success(self, mock_repository, client):
        """Тест успешной отмены теста"""
        # Мокаем репозиторий
        test_id = "tst_123456"
        
        mock_test = TestResultsResponse(
            test_id=test_id,
            status=TestStatus.RUNNING,
            passed=False,
            results={},
            created_at="2024-01-01T00:00:00"
        )
        
        mock_repository.get_test = MagicMock(return_value=mock_test)
        mock_repository.update_test_results = MagicMock(return_value=True)
        
        # Отправляем запрос
        response = client.post(f"/tests/{test_id}/cancel")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert test_id in data["message"]
    
    @patch("app.main.test_repository")
    def test_cancel_test_not_found(self, mock_repository, client):
        """Тест отмены несуществующего теста"""
        # Мокаем репозиторий
        test_id = "nonexistent"
        
        mock_repository.get_test = MagicMock(return_value=None)
        
        # Отправляем запрос
        response = client.post(f"/tests/{test_id}/cancel")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert test_id in data["detail"]
    
    @patch("app.main.test_repository")
    def test_cancel_test_already_completed(self, mock_repository, client):
        """Тест отмены уже завершенного теста"""
        # Мокаем репозиторий
        test_id = "tst_123456"
        
        mock_test = TestResultsResponse(
            test_id=test_id,
            status=TestStatus.COMPLETED,
            passed=True,
            results={},
            created_at="2024-01-01T00:00:00",
            completed_at="2024-01-01T00:01:00"
        )
        
        mock_repository.get_test = MagicMock(return_value=mock_test)
        
        # Отправляем запрос
        response = client.post(f"/tests/{test_id}/cancel")
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "Cannot cancel test" in data["detail"]
    
    def test_invalid_json_request(self, client):
        """Тест запроса с невалидным JSON"""
        # Отправляем невалидный JSON
        response = client.post("/test", data="invalid json", headers={"Content-Type": "application/json"})
        
        assert response.status_code == 422  # Validation error
    
    def test_docs_endpoint(self, client):
        """Тест доступности документации OpenAPI"""
        response = client.get("/docs")
        
        # Документация должна быть доступна
        assert response.status_code == 200
    
    def test_openapi_endpoint(self, client):
        """Тест доступности спецификации OpenAPI"""
        response = client.get("/openapi.json")
        
        # Спецификация должна быть доступна
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем основные поля OpenAPI
        assert "openapi" in data
        assert "info" in data
        assert "paths" in data
        assert data["info"]["title"] == "C20.4 Test Runner"