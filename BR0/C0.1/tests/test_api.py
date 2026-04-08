import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
import os

# Добавляем путь к родительскому каталогу для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from main import app
from models import ContainerStatus, ContainerInfo


client = TestClient(app)


class TestHealthCheck:
    """Тесты для эндпоинта /health"""
    
    @patch("BR0.C0.1.main.docker_service.check_docker_daemon")
    @patch("BR0.C0.1.main.docker_service.list_containers")
    def test_health_check_healthy(self, mock_list_containers, mock_check_daemon):
        """Тест healthcheck когда всё работает"""
        mock_check_daemon.return_value = True
        mock_list_containers.return_value = [
            ContainerInfo(
                name="container1",
                status=ContainerStatus.RUNNING,
                image="test:latest",
                ports=[],
                created="2024-01-01T00:00:00Z"
            ),
            ContainerInfo(
                name="container2",
                status=ContainerStatus.STOPPED,
                image="test:latest",
                ports=[],
                created="2024-01-01T00:00:00Z"
            )
        ]
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["docker_daemon"] is True
        assert data["containers_running"] == 1
        assert data["containers_total"] == 2
    
    @patch("BR0.C0.1.main.docker_service.check_docker_daemon")
    def test_health_check_unhealthy(self, mock_check_daemon):
        """Тест healthcheck когда Docker недоступен"""
        mock_check_daemon.return_value = False
        
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["docker_daemon"] is False


class TestListContainers:
    """Тесты для эндпоинта /containers"""
    
    @patch("BR0.C0.1.main.docker_service.list_containers")
    def test_list_containers_success(self, mock_list_containers):
        """Тест успешного получения списка контейнеров"""
        mock_list_containers.return_value = [
            ContainerInfo(
                name="container1",
                status=ContainerStatus.RUNNING,
                image="test:latest",
                ports=["80/tcp"],
                created="2024-01-01T00:00:00Z"
            )
        ]
        
        response = client.get("/containers")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "container1"
        assert data[0]["status"] == "running"
    
    @patch("BR0.C0.1.main.docker_service.list_containers")
    def test_list_containers_all(self, mock_list_containers):
        """Тест получения всех контейнеров (включая остановленные)"""
        mock_list_containers.return_value = []
        
        response = client.get("/containers?all=true")
        
        assert response.status_code == 200
        mock_list_containers.assert_called_once_with(all_containers=True)
    
    @patch("BR0.C0.1.main.docker_service.list_containers")
    def test_list_containers_error(self, mock_list_containers):
        """Тест ошибки при получении списка контейнеров"""
        mock_list_containers.side_effect = Exception("Docker error")
        
        response = client.get("/containers")
        
        assert response.status_code == 500
        assert "Failed to list containers" in response.json()["detail"]


class TestContainerStatus:
    """Тесты для эндпоинта /containers/{name}/status"""
    
    @patch("BR0.C0.1.main.docker_service.get_container_status")
    def test_get_container_status_success(self, mock_get_status):
        """Тест успешного получения статуса контейнера"""
        mock_get_status.return_value = ContainerInfo(
            name="test-container",
            status=ContainerStatus.RUNNING,
            image="test:latest",
            ports=["80/tcp"],
            created="2024-01-01T00:00:00Z",
            health="healthy"
        )
        
        response = client.get("/containers/test-container/status")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "test-container"
        assert data["status"] == "running"
        assert data["health"] == "healthy"
    
    @patch("BR0.C0.1.main.docker_service.get_container_status")
    def test_get_container_status_error(self, mock_get_status):
        """Тест ошибки при получении статуса контейнера"""
        mock_get_status.side_effect = Exception("Container not found")
        
        response = client.get("/containers/nonexistent/status")
        
        assert response.status_code == 500
        assert "Failed to get status" in response.json()["detail"]


class TestContainerActions:
    """Тесты для эндпоинтов управления контейнерами"""
    
    @patch("BR0.C0.1.main.docker_service.start_container")
    @patch("BR0.C0.1.main.logging_service.log_container_action")
    def test_start_container_success(self, mock_log_action, mock_start_container):
        """Тест успешного запуска контейнера"""
        mock_start_container.return_value = {
            "success": True,
            "message": "Container started",
            "container_name": "test-container",
            "action": "start"
        }
        
        response = client.post(
            "/containers/test-container/start",
            json={"force": False, "timeout": None}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "start"
        mock_start_container.assert_called_once_with(
            container_name="test-container",
            force=False
        )
    
    @patch("BR0.C0.1.main.docker_service.start_container")
    def test_start_container_error(self, mock_start_container):
        """Тест ошибки при запуске контейнера"""
        mock_start_container.side_effect = Exception("Docker error")
        
        response = client.post(
            "/containers/test-container/start",
            json={"force": True}
        )
        
        assert response.status_code == 500
        assert "Failed to start container" in response.json()["detail"]
    
    @patch("BR0.C0.1.main.docker_service.stop_container")
    @patch("BR0.C0.1.main.logging_service.log_container_action")
    def test_stop_container_success(self, mock_log_action, mock_stop_container):
        """Тест успешной остановки контейнера"""
        mock_stop_container.return_value = {
            "success": True,
            "message": "Container stopped",
            "container_name": "test-container",
            "action": "stop"
        }
        
        response = client.post(
            "/containers/test-container/stop",
            json={"force": False, "timeout": 10}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "stop"
        mock_stop_container.assert_called_once_with(
            container_name="test-container",
            timeout=10
        )
    
    @patch("BR0.C0.1.main.docker_service.restart_container")
    @patch("BR0.C0.1.main.logging_service.log_container_action")
    def test_restart_container_success(self, mock_log_action, mock_restart_container):
        """Тест успешного перезапуска контейнера"""
        mock_restart_container.return_value = {
            "success": True,
            "message": "Container restarted",
            "container_name": "test-container",
            "action": "restart"
        }
        
        response = client.post(
            "/containers/test-container/restart",
            json={"force": False, "timeout": 5}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["action"] == "restart"
        mock_restart_container.assert_called_once_with(
            container_name="test-container",
            timeout=5
        )


class TestRootEndpoint:
    """Тесты для корневого эндпоинта"""
    
    def test_root(self):
        """Тест корневого эндпоинта"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "C0.1 - Оркестратор среды (Гермес)"
        assert data["version"] == "1.0.0"
        assert "endpoints" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])