from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConfigCreate(BaseModel):
    """Модель для создания новой версии конфигурации"""
    content: str = Field(..., description="Содержимое конфигурации")
    version: str = Field(..., description="Версия конфигурации (например, v1.0.0)")
    description: Optional[str] = Field(None, description="Описание изменений")
    config_type: str = Field("docker-compose", description="Тип конфигурации: docker-compose, env, etc.")


class ConfigResponse(BaseModel):
    """Модель ответа с информацией о конфигурации"""
    id: int
    version: str
    config_type: str
    description: Optional[str]
    created_at: datetime
    hash: str
    size_bytes: int


class ConfigContentResponse(BaseModel):
    """Модель ответа с содержимым конфигурации"""
    id: int
    version: str
    config_type: str
    description: Optional[str]
    content: str
    created_at: datetime
    hash: str
    size_bytes: int


class ConfigDiffRequest(BaseModel):
    """Модель запроса для получения разницы между версиями"""
    from_version: str = Field(..., description="Исходная версия")
    to_version: str = Field(..., description="Целевая версия")


class ConfigDiffResponse(BaseModel):
    """Модель ответа с разницей между версиями"""
    from_version: str
    to_version: str
    diff: str
    changes_count: int


class RollbackRequest(BaseModel):
    """Модель запроса для отката к версии"""
    target_version: Optional[str] = Field(None, description="Версия для отката (если не указана, используется версия из пути)")
    create_new_version: bool = Field(True, description="Создать новую версию с откатом")


class HealthResponse(BaseModel):
    """Модель ответа healthcheck"""
    status: str
    version_count: int
    database_status: str
    timestamp: datetime