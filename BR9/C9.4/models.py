from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class DialogRequest(BaseModel):
    message: str = Field(..., min_length=1)
    project_id: str = Field(..., min_length=1)


class DialogResponse(BaseModel):
    session_id: str
    reply: str
    completed: bool = False
    task_id: Optional[str] = None


class L2Specification(BaseModel):
    """Pydantic модель для валидации L2 (Паспорт системы)."""
    title: str = Field(..., min_length=1, description="Название проекта")
    description: str = Field(..., min_length=1, description="Описание проекта")
    requirements: List[str] = Field(..., description="Список требований")
    technical_specs: Dict[str, Any] = Field(..., description="Технические спецификации")
