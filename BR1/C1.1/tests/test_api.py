import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from ..main import app


class TestCognitiveEngineAPI:
    """Тесты для API когнитивного движка"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Тест корневого эндпоинта"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["service"] == "Cognitive Engine (Дедал)"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data
        assert "POST /analyze" in data["endpoints"]
        assert "POST /hypothesis" in data["endpoints"]
        assert "GET /health" in data["endpoints"]
    
    def test_health_check(self, client):
        """Тест healthcheck эндпоинта"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "dependencies" in data
        assert "uptime_seconds" in data
    
    @patch("..main.cognitive_service.analyze_logs")
    def test_analyze_endpoint(self, mock_analyze, client):
        """Тест эндпоинта анализа"""
        # Мокаем ответ сервиса
        mock_report = {
            "period_start": "2026-04-05T10:00:00",
            "period_end": "2026-04-06T10:00:00",
            "total_logs_analyzed": 1500,
            "error_count": 33,
            "error_types": {"timeout": 15, "connection_error": 8},
            "containers_with_issues": ["C0.1", "C6.2"],
            "generated_hypotheses": ["Увеличить таймауты"],
            "recommendations": ["Проверить конфигурацию"],
            "analysis_duration_seconds": 0.5
        }
        mock_analyze.return_value = type('obj', (object,), {'dict': lambda: mock_report})()
        
        # Отправляем запрос
        request_data = {"period_hours": 24, "container_filter": "C0.1"}
        response = client.post("/analyze", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "report" in data
        assert data["report"]["error_count"] == 33
        assert "C0.1" in data["report"]["containers_with_issues"]
        assert "message" in data
        
        # Проверяем, что сервис был вызван с правильными параметрами
        mock_analyze.assert_called_once_with(period_hours=24, container_filter="C0.1")
    
    @patch("..main.cognitive_service.analyze_logs")
    def test_analyze_endpoint_default_params(self, mock_analyze, client):
        """Тест эндпоинта анализа с параметрами по умолчанию"""
        mock_report = {
            "period_start": "2026-04-05T10:00:00",
            "period_end": "2026-04-06T10:00:00",
            "total_logs_analyzed": 1500,
            "error_count": 33,
            "error_types": {},
            "containers_with_issues": [],
            "generated_hypotheses": [],
            "recommendations": [],
            "analysis_duration_seconds": 0.5
        }
        mock_analyze.return_value = type('obj', (object,), {'dict': lambda: mock_report})()
        
        # Отправляем запрос только с period_hours
        request_data = {"period_hours": 12}
        response = client.post("/analyze", json=request_data)
        
        assert response.status_code == 200
        mock_analyze.assert_called_once_with(period_hours=12, container_filter=None)
    
    @patch("..main.cognitive_service.create_hypothesis_task")
    def test_hypothesis_endpoint(self, mock_create_task, client):
        """Тест эндпоинта создания гипотезы"""
        # Мокаем ответ сервиса
        mock_task = {
            "hypothesis_id": "abc123",
            "hypothesis_text": "Увеличить таймауты в контейнере C0.1",
            "priority": "high",
            "created_at": "2026-04-05T10:00:00",
            "status": "pending",
            "assigned_to": "Cline",
            "handover_task_id": "handover_task_12345"
        }
        mock_create_task.return_value = type('obj', (object,), {'dict': lambda: mock_task})()
        
        # Отправляем запрос
        request_data = {
            "hypothesis_text": "Увеличить таймауты в контейнере C0.1",
            "priority": "high",
            "related_containers": ["C0.1", "C6.2"],
            "estimated_impact": "Уменьшение ошибок timeout на 50%"
        }
        response = client.post("/hypothesis", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "task" in data
        assert data["task"]["hypothesis_id"] == "abc123"
        assert data["task"]["assigned_to"] == "Cline"
        assert "message" in data
        
        # Проверяем, что сервис был вызван с правильными параметрами
        mock_create_task.assert_called_once_with(
            hypothesis_text="Увеличить таймауты в контейнере C0.1",
            priority="high",
            related_containers=["C0.1", "C6.2"]
        )
    
    @patch("..main.cognitive_service.create_hypothesis_task")
    def test_hypothesis_endpoint_default_params(self, mock_create_task, client):
        """Тест эндпоинта создания гипотезы с параметрами по умолчанию"""
        mock_task = {
            "hypothesis_id": "def456",
            "hypothesis_text": "Тестовая гипотеза",
            "priority": "medium",
            "created_at": "2026-04-05T10:00:00",
            "status": "pending",
            "assigned_to": "Cline",
            "handover_task_id": "handover_task_67890"
        }
        mock_create_task.return_value = type('obj', (object,), {'dict': lambda: mock_task})()
        
        # Отправляем запрос только с обязательным полем
        request_data = {"hypothesis_text": "Тестовая гипотеза"}
        response = client.post("/hypothesis", json=request_data)
        
        assert response.status_code == 200
        mock_create_task.assert_called_once_with(
            hypothesis_text="Тестовая гипотеза",
            priority="medium",
            related_containers=[]
        )
    
    @patch("..main.cognitive_service.get_hypothesis_task")
    def test_get_hypothesis_endpoint(self, mock_get_task, client):
        """Тест эндпоинта получения гипотезы по ID"""
        # Мокаем ответ сервиса
        mock_task = {
            "hypothesis_id": "abc123",
            "hypothesis_text": "Тестовая гипотеза",
            "priority": "medium",
            "created_at": "2026-04-05T10:00:00",
            "status": "pending",
            "assigned_to": "Cline",
            "handover_task_id": "handover_task_12345"
        }
        mock_get_task.return_value = type('obj', (object,), {'dict': lambda: mock_task})()
        
        response = client.get("/hypothesis/abc123")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert "task" in data
        assert data["task"]["hypothesis_id"] == "abc123"
        
        mock_get_task.assert_called_once_with("abc123")
    
    @patch("..main.cognitive_service.get_hypothesis_task")
    def test_get_hypothesis_endpoint_not_found(self, mock_get_task, client):
        """Тест эндпоинта получения несуществующей гипотезы"""
        mock_get_task.return_value = None
        
        response = client.get("/hypothesis/non_existent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "не найдена" in data["detail"]
    
    @patch("..main.cognitive_service.list_hypothesis_tasks")
    def test_list_hypotheses_endpoint(self, mock_list_tasks, client):
        """Тест эндпоинта списка гипотез"""
        # Мокаем ответ сервиса
        mock_tasks = [
            type('obj', (object,), {'dict': lambda: {
                "hypothesis_id": "task1",
                "hypothesis_text": "Гипотеза 1",
                "priority": "low",
                "created_at": "2026-04-05T10:00:00",
                "status": "pending",
                "assigned_to": "Cline",
                "handover_task_id": "handover_1"
            }})(),
            type('obj', (object,), {'dict': lambda: {
                "hypothesis_id": "task2",
                "hypothesis_text": "Гипотеза 2",
                "priority": "high",
                "created_at": "2026-04-05T11:00:00",
                "status": "in_progress",
                "assigned_to": "Гефест",
                "handover_task_id": "handover_2"
            }})()
        ]
        mock_list_tasks.return_value = mock_tasks
        
        # Тест без фильтра
        response = client.get("/hypothesis")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "success"
        assert data["count"] == 2
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["hypothesis_id"] == "task1"
        assert data["tasks"][1]["hypothesis_id"] == "task2"
        
        mock_list_tasks.assert_called_once_with(status=None)
    
    @patch("..main.cognitive_service.list_hypothesis_tasks")
    def test_list_hypotheses_endpoint_with_filter(self, mock_list_tasks, client):
        """Тест эндпоинта списка гипотез с фильтром статуса"""
        mock_tasks = [
            type('obj', (object,), {'dict': lambda: {
                "hypothesis_id": "task1",
                "hypothesis_text": "Гипотеза 1",
                "priority": "low",
                "created_at": "2026-04-05T10:00:00",
                "status": "pending",
                "assigned_to": "Cline",
                "handover_task_id": "handover_1"
            }})()
        ]
        mock_list_tasks.return_value = mock_tasks
        
        # Тест с фильтром статуса
        response = client.get("/hypothesis?status=pending")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["count"] == 1
        mock_list_tasks.assert_called_once_with(status="pending")
    
    def test_analyze_endpoint_validation_error(self, client):
        """Тест валидации входных данных для анализа"""
        # Неправильный тип данных
        request_data = {"period_hours": "не число"}
        response = client.post("/analyze", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_hypothesis_endpoint_validation_error(self, client):
        """Тест валидации входных данных для гипотезы"""
        # Отсутствует обязательное поле
        request_data = {"priority": "high"}
        response = client.post("/hypothesis", json=request_data)
        
        assert response.status_code == 422  # Validation error
        
        # Неправильный приоритет
        request_data = {"hypothesis_text": "Тест", "priority": "invalid"}
        response = client.post("/hypothesis", json=request_data)
        
        assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])