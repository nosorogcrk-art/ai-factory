import subprocess
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import httpx

from .models import ContainerInfo, ContainerStatus, ContainerActionResponse


logger = logging.getLogger(__name__)


class DockerService:
    """Сервис для работы с Docker через CLI"""
    
    def __init__(self, docker_socket: str = "/var/run/docker.sock"):
        self.docker_socket = docker_socket
    
    def _run_docker_command(self, command: List[str]) -> Dict[str, Any]:
        """Выполнить команду Docker и вернуть результат"""
        try:
            result = subprocess.run(
                ["docker"] + command,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    "success": True,
                    "output": result.stdout.strip(),
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "output": result.stdout.strip(),
                    "error": result.stderr.strip()
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": "Command timeout"
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": str(e)
            }
    
    def get_container_status(self, container_name: str) -> ContainerInfo:
        """Получить статус контейнера"""
        result = self._run_docker_command([
            "inspect",
            "--format={{json .}}",
            container_name
        ])
        
        if not result["success"]:
            # Контейнер не найден или ошибка
            return ContainerInfo(
                name=container_name,
                status=ContainerStatus.UNKNOWN,
                image="unknown",
                ports=[],
                created="",
                health=None,
                exit_code=None
            )
        
        try:
            data = json.loads(result["output"])
            state = data.get("State", {})
            config = data.get("Config", {})
            network = data.get("NetworkSettings", {})
            
            # Определяем статус
            status_str = state.get("Status", "").lower()
            if status_str == "running":
                status = ContainerStatus.RUNNING
            elif status_str == "exited":
                status = ContainerStatus.STOPPED
            elif status_str == "paused":
                status = ContainerStatus.PAUSED
            elif status_str == "restarting":
                status = ContainerStatus.RESTARTING
            elif status_str == "dead":
                status = ContainerStatus.DEAD
            else:
                status = ContainerStatus.UNKNOWN
            
            # Проверяем health status
            health = None
            if state.get("Health"):
                health_status = state["Health"].get("Status", "")
                if health_status == "unhealthy":
                    status = ContainerStatus.UNHEALTHY
                    health = health_status
            
            # Получаем порты
            ports = []
            ports_data = network.get("Ports", {})
            if ports_data:
                for port, bindings in ports_data.items():
                    if bindings:
                        for binding in bindings:
                            ports.append(f"{binding.get('HostIp', '0.0.0.0')}:{binding.get('HostPort')}->{port}")
                    else:
                        ports.append(port)
            
            return ContainerInfo(
                name=container_name,
                status=status,
                image=config.get("Image", ""),
                ports=ports,
                created=data.get("Created", ""),
                health=health,
                exit_code=state.get("ExitCode")
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing docker inspect: {e}")
            return ContainerInfo(
                name=container_name,
                status=ContainerStatus.UNKNOWN,
                image="unknown",
                ports=[],
                created="",
                health=None,
                exit_code=None
            )
    
    def start_container(self, container_name: str, force: bool = False) -> ContainerActionResponse:
        """Запустить контейнер"""
        command = ["start"]
        if force:
            command.append("--force")
        command.append(container_name)
        
        result = self._run_docker_command(command)
        
        if result["success"]:
            message = f"Container {container_name} started successfully"
            logger.info(message)
            return ContainerActionResponse(
                success=True,
                message=message,
                container_name=container_name,
                action="start"
            )
        else:
            message = f"Failed to start container {container_name}: {result['error']}"
            logger.error(message)
            return ContainerActionResponse(
                success=False,
                message=message,
                container_name=container_name,
                action="start",
                details={"error": result["error"]}
            )
    
    def stop_container(self, container_name: str, timeout: Optional[int] = None) -> ContainerActionResponse:
        """Остановить контейнер"""
        command = ["stop"]
        if timeout:
            command.extend(["--time", str(timeout)])
        command.append(container_name)
        
        result = self._run_docker_command(command)
        
        if result["success"]:
            message = f"Container {container_name} stopped successfully"
            logger.info(message)
            return ContainerActionResponse(
                success=True,
                message=message,
                container_name=container_name,
                action="stop"
            )
        else:
            message = f"Failed to stop container {container_name}: {result['error']}"
            logger.error(message)
            return ContainerActionResponse(
                success=False,
                message=message,
                container_name=container_name,
                action="stop",
                details={"error": result["error"]}
            )
    
    def restart_container(self, container_name: str, timeout: Optional[int] = None) -> ContainerActionResponse:
        """Перезапустить контейнер"""
        command = ["restart"]
        if timeout:
            command.extend(["--time", str(timeout)])
        command.append(container_name)
        
        result = self._run_docker_command(command)
        
        if result["success"]:
            message = f"Container {container_name} restarted successfully"
            logger.info(message)
            return ContainerActionResponse(
                success=True,
                message=message,
                container_name=container_name,
                action="restart"
            )
        else:
            message = f"Failed to restart container {container_name}: {result['error']}"
            logger.error(message)
            return ContainerActionResponse(
                success=False,
                message=message,
                container_name=container_name,
                action="restart",
                details={"error": result["error"]}
            )
    
    def list_containers(self, all_containers: bool = False) -> List[ContainerInfo]:
        """Получить список всех контейнеров"""
        command = ["ps", "--format={{json .}}"]
        if all_containers:
            command.append("-a")
        
        result = self._run_docker_command(command)
        
        if not result["success"]:
            return []
        
        containers = []
        for line in result["output"].strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                container_info = ContainerInfo(
                    name=data.get("Names", ""),
                    status=ContainerStatus(data.get("State", "").lower()),
                    image=data.get("Image", ""),
                    ports=data.get("Ports", "").split(",") if data.get("Ports") else [],
                    created=data.get("CreatedAt", ""),
                    health=None,
                    exit_code=None
                )
                containers.append(container_info)
            except (json.JSONDecodeError, ValueError):
                continue
        
        return containers
    
    def check_docker_daemon(self) -> bool:
        """Проверить доступность Docker демона"""
        result = self._run_docker_command(["version", "--format={{json .}}"])
        return result["success"]


class LoggingService:
    """Сервис для отправки логов в BR18"""
    
    def __init__(self, br18_url: str = "http://br18:8108"):
        self.br18_url = br18_url
        self.client = httpx.AsyncClient(timeout=10.0)
    
    async def send_log(self, log_entry: Dict[str, Any]) -> bool:
        """Отправить лог в BR18"""
        try:
            response = await self.client.post(
                f"{self.br18_url}/logs",
                json=log_entry
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")
            return False
    
    async def log_container_action(
        self,
        container_name: str,
        action: str,
        success: bool,
        message: str
    ) -> None:
        """Записать лог о действии с контейнером"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "INFO" if success else "ERROR",
            "container": container_name,
            "action": action,
            "message": message,
            "success": success
        }
        
        # Отправляем в BR18
        await self.send_log(log_entry)
        
        # Также пишем в локальный лог
        if success:
            logger.info(f"{action} {container_name}: {message}")
        else:
            logger.error(f"{action} {container_name}: {message}")


# Создаём глобальные экземпляры сервисов
docker_service = DockerService()
logging_service = LoggingService()