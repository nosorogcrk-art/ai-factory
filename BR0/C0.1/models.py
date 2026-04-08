from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from enum import Enum


class ContainerStatus(str, Enum):
    RUNNING = "running"
    STOPPED = "stopped"
    PAUSED = "paused"
    RESTARTING = "restarting"
    DEAD = "dead"
    UNKNOWN = "unknown"
    UNHEALTHY = "unhealthy"


class ContainerInfo(BaseModel):
    name: str
    status: ContainerStatus
    image: str
    ports: List[str]
    created: str
    health: Optional[str] = None
    exit_code: Optional[int] = None


class ContainerActionRequest(BaseModel):
    force: bool = False
    timeout: Optional[int] = None


class ContainerActionResponse(BaseModel):
    success: bool
    message: str
    container_name: str
    action: str
    details: Optional[Dict[str, Any]] = None


class HealthCheckResponse(BaseModel):
    status: str
    timestamp: str
    uptime: float
    docker_daemon: bool
    containers_running: int
    containers_total: int


class LogEntry(BaseModel):
    timestamp: str
    level: str
    container: str
    action: str
    message: str
    success: bool