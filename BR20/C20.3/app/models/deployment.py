from datetime import datetime
from typing import Optional, List
from enum import Enum
from pydantic import BaseModel, Field


class DeploymentStatus(str, Enum):
    """Статусы деплоя"""
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class RollbackStatus(str, Enum):
    """Статусы отката"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class DeploymentCreate(BaseModel):
    """Модель для создания записи о деплое"""
    deploy_id: str = Field(..., description="Уникальный ID деплоя")
    repository: str = Field(..., description="Название репозитория")
    commit_hash: str = Field(..., description="Хеш коммита")
    tag: Optional[str] = Field(None, description="Тег версии")
    environment: str = Field(..., description="Окружение (production, staging, etc.)")
    config_files: List[str] = Field(default_factory=list, description="Список конфигурационных файлов")
    description: Optional[str] = Field(None, description="Описание деплоя")


class DeploymentResponse(BaseModel):
    """Модель ответа с информацией о деплое"""
    id: int
    deploy_id: str
    repository: str
    commit_hash: str
    tag: Optional[str]
    environment: str
    config_files: List[str]
    description: Optional[str]
    status: DeploymentStatus
    created_at: datetime


class RollbackRequest(BaseModel):
    """Модель запроса для отката"""
    deploy_id: Optional[str] = Field(None, description="ID деплоя для отката")
    target_version: Optional[str] = Field(None, description="Целевая версия для отката")
    reason: str = Field(..., description="Причина отката")
    environment: Optional[str] = Field(None, description="Окружение (если не указан deploy_id)")


class RollbackResponse(BaseModel):
    """Модель ответа с информацией об откате"""
    rollback_id: str
    status: RollbackStatus
    message: str
    deploy_id: Optional[str] = None
    target_version: Optional[str] = None
    created_at: datetime


class RollbackHistoryResponse(BaseModel):
    """Модель ответа с историей откатов"""
    id: int
    rollback_id: str
    deploy_id: str
    target_version: str
    reason: str
    status: RollbackStatus
    created_at: datetime
    completed_at: Optional[datetime]


class HealthResponse(BaseModel):
    """Модель ответа healthcheck"""
    status: str
    deployment_count: int
    rollback_count: int
    database_status: str
    timestamp: datetime


class AlertNotification(BaseModel):
    """Модель уведомления от Alert Manager (BR18)"""
    alert_id: str = Field(..., description="ID алерта")
    severity: str = Field(..., description="Серьезность (critical, warning, info)")
    message: str = Field(..., description="Сообщение алерта")
    deploy_id: Optional[str] = Field(None, description="ID деплоя, связанного с алертом")
    environment: Optional[str] = Field(None, description="Окружение")
    timestamp: datetime = Field(..., description="Время создания алерта")