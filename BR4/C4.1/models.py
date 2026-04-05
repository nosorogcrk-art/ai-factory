"""Pydantic-модели для Project Dashboard."""

from pydantic import BaseModel
from typing import Dict, Any, List, Optional


class MetricsResponse(BaseModel):
    """Ответ эндпоинта /api/status."""
    metrics: Dict[str, Any]
    branches: List[Dict[str, Any]]
    tasks: List[Dict[str, Any]]
    skill_stats: Dict[str, int]
    last_update: str