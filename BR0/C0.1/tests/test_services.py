import pytest
from unittest.mock import Mock, patch
import json
import sys
import os

# Добавляем путь к родительскому каталогу для импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models import ContainerStatus
from services import DockerService, LoggingService


class TestDockerService:
    """Тесты для DockerService"""
    
    def setup_method(self):
        self.docker_service = DockerService()
    
    @patch("services.subprocess.run")
    def test_run_docker_command_success(self, mock_run):
        """Тест успешного выполнения команды Docker"""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = self.docker_service._run_docker_command(["ps"])
        
        assert result["success"] is True
        assert result["output"] == "output"
        assert result["error"] is None
        mock_run.assert_called_once()
    
    @patch("services.subprocess.run")
    def test_run_docker_command_failure(self, mock_run):
        """Тест неудачного выполнения команды Docker"""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"
        mock_run.return_value = mock_result
        
        result = self.docker_service._run_docker_command(["ps"])
        
        assert result["success"] is False
        assert result["output"] == ""
        assert result["error"] == "error"
    
    @patch("services.subprocess.run")
    def test_run_docker_command_timeout(self, mock_run):
        """Тест таймаута команды Docker"""
        mock_run.side_effect = TimeoutError("Command timeout")
        
        result = self.docker_service._run_docker_command(["ps"])
        
        assert result["success"] is False
        assert result["error"] == "Command timeout"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_get_container_status_success(self, mock_run):
        """Тест получения статуса контейнера (успех)"""
        container_data = {
            "State": {
                "Status": "running",
                "Health": {"Status": "healthy"},
                "ExitCode": 0
            },
            "Config": {"Image": "test:latest"},
            "NetworkSettings": {
                "Ports": {
                    "80/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8080"}]
                }
            },
            "Created": "2024-01-01T00:00:00Z"
        }
        
        mock_run.return_value = {
            "success": True,
            "output": json.dumps(container_data),
            "error": None
        }
        
        result = self.docker_service.get_container_status("test-container")
        
        assert result.name == "test-container"
        assert result.status == ContainerStatus.RUNNING
        assert result.image == "test:latest"
        assert result.ports == ["0.0.0.0:8080->80/tcp"]
        assert result.health == "healthy"
        assert result.exit_code == 0
    
    @patch.object(DockerService, '_run_docker_command')
    def test_get_container_status_not_found(self, mock_run):
        """Тест получения статуса несуществующего контейнера"""
        mock_run.return_value = {
            "success": False,
            "output": "",
            "error": "No such container"
        }
        
        result = self.docker_service.get_container_status("nonexistent")
        
        assert result.name == "nonexistent"
        assert result.status == ContainerStatus.UNKNOWN
        assert result.image == "unknown"
        assert result.ports == []
    
    @patch.object(DockerService, '_run_docker_command')
    def test_get_container_status_unhealthy(self, mock_run):
        """Тест получения статуса нездорового контейнера"""
        container_data = {
            "State": {
                "Status": "running",
                "Health": {"Status": "unhealthy"},
                "ExitCode": 0
            },
            "Config": {"Image": "test:latest"},
            "NetworkSettings": {"Ports": {}},
            "Created": "2024-01-01T00:00:00Z"
        }
        
        mock_run.return_value = {
            "success": True,
            "output": json.dumps(container_data),
            "error": None
        }
        
        result = self.docker_service.get_container_status("unhealthy-container")
        
        assert result.status == ContainerStatus.UNHEALTHY
        assert result.health == "unhealthy"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_start_container_success(self, mock_run):
        """Тест успешного запуска контейнера"""
        mock_run.return_value = {
            "success": True,
            "output": "",
            "error": None
        }
        
        result = self.docker_service.start_container("test-container")
        
        assert result.success is True
        assert "started successfully" in result.message
        assert result.container_name == "test-container"
        assert result.action == "start"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_start_container_failure(self, mock_run):
        """Тест неудачного запуска контейнера"""
        mock_run.return_value = {
            "success": False,
            "output": "",
            "error": "Container not found"
        }
        
        result = self.docker_service.start_container("nonexistent")
        
        assert result.success is False
        assert "Failed to start" in result.message
        assert result.details["error"] == "Container not found"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_stop_container_success(self, mock_run):
        """Тест успешной остановки контейнера"""
        mock_run.return_value = {
            "success": True,
            "output": "",
            "error": None
        }
        
        result = self.docker_service.stop_container("test-container", timeout=10)
        
        assert result.success is True
        assert "stopped successfully" in result.message
        assert result.action == "stop"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_restart_container_success(self, mock_run):
        """Тест успешного перезапуска контейнера"""
        mock_run.return_value = {
            "success": True,
            "output": "",
            "error": None
        }
        
        result = self.docker_service.restart_container("test-container", timeout=5)
        
        assert result.success is True
        assert "restarted successfully" in result.message
        assert result.action == "restart"
    
    @patch.object(DockerService, '_run_docker_command')
    def test_list_containers(self, mock_run):
        """Тест получения списка контейнеров"""
        container_data = [
            {
                "Names": "container1",
                "State": "running",
                "Image": "image1:latest",
                "Ports": "80/tcp",
                "CreatedAt": "2024-01-01T00:00:00Z"
            },
            {
                "Names": "container2",
                "State": "exited",
                "Image": "image2:latest",
                "Ports": "",
                "CreatedAt": "2024-01-01T00:00:00Z"
            }
        ]
        
        mock_run.return_value = {
            "success": True,
            "output": "\n".join(json.dumps(c) for c in container_data),
            "error": None
        }
        
        result = self.docker_service.list_containers()
        
        assert len(result) == 2
        assert result[0].name == "container1"
        assert result[0].status == ContainerStatus.RUNNING
        assert result[1].name == "container2"
        assert result[1].status == ContainerStatus.STOPPED
    
    @patch.object(DockerService, '_run_docker_command')
    def test_check_docker_daemon_success(self, mock_run):
        """Тест проверки доступности Docker демона (успех)"""
        mock_run.return_value = {
            "success": True,
            "output": '{"Version": "20.10.0"}',
            "error": None
        }
        
        result = self.docker_service.check_docker_daemon()
        
        assert result is True
    
    @patch.object(DockerService, '_run_docker_command')
    def test_check_docker_daemon_failure(self, mock_run):
        """Тест проверки доступности Docker демона (ошибка)"""
        mock_run.return_value = {
            "success": False,
            "output": "",
            "error": "Cannot connect to Docker daemon"
        }
        
        result = self.docker_service.check_docker_daemon()
        
        assert result is False


class TestLoggingService:
    """Тесты для LoggingService"""
    
    def setup_method(self):
        self.logging_service = LoggingService(br18_url="http://test:8000")
    
    @pytest.mark.asyncio
    @patch("services.httpx.AsyncClient.post")
    async def test_send_log_success(self, mock_post):
        """Тест успешной отправки лога"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        log_entry = {"test": "data"}
        result = await self.logging_service.send_log(log_entry)
        
        assert result is True
        mock_post.assert_called_once_with(
            "http://test:8000/logs",
            json=log_entry
        )
    
    @pytest.mark.asyncio
    @patch("services.httpx.AsyncClient.post")
    async def test_send_log_failure(self, mock_post):
        """Тест неудачной отправки лога"""
        mock_post.side_effect = Exception("Connection error")
        
        log_entry = {"test": "data"}
        result = await self.logging_service.send_log(log_entry)
        
        assert result is False
    
    @pytest.mark.asyncio
    @patch.object(LoggingService, 'send_log')
    async def test_log_container_action(self, mock_send_log):
        """Тест логирования действия с контейнером"""
        mock_send_log.return_value = True
        
        await self.logging_service.log_container_action(
            container_name="test-container",
            action="start",
            success=True,
            message="Container started"
        )
        
        mock_send_log.assert_called_once()
        call_args = mock_send_log.call_args[0][0]
        assert call_args["container"] == "test-container"
        assert call_args["action"] == "start"
        assert call_args["success"] is True
        assert call_args["message"] == "Container started"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])