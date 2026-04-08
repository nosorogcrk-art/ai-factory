from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime


class AnalyzeRequest(BaseModel):
    """Запрос на анализ логов и метрик"""
    period_hours: int = 24
    container_filter: Optional[str] = None
    error_threshold: Optional[int] = None


class HypothesisRequest(BaseModel):
    """Запрос на создание гипотезы"""
    hypothesis_text: str
    priority: str = "medium"  # low, medium, high, critical
    related_containers: List[str] = []
    estimated_impact: Optional[str] = None


class ExternalArticle(BaseModel):
    source: str
    source_name: str
    title: str
    url: str
    summary: str
    published: Optional[str] = None


class AnalysisReport(BaseModel):
    """Отчёт анализа"""
    period_start: datetime
    period_end: datetime
    total_logs_analyzed: int
    error_count: int
    error_types: Dict[str, int]
    containers_with_issues: List[str]
    generated_hypotheses: List[str]
    recommendations: List[str]
    analysis_duration_seconds: float
    evidence: Dict[str, List[dict]] = {}  # новое поле
    reva_feedback: List[dict] = []  # отчёты Ревы
    github_evidence: Dict[str, List[dict]] = {}  # GitHub доказательства
    external_insights: List[ExternalArticle] = []  # Внешние статьи (RSS, arXiv)


class HypothesisTask(BaseModel):
    """Задача на основе гипотезы"""
    hypothesis_id: str
    hypothesis_text: str
    priority: str
    created_at: datetime
    status: str = "pending"  # pending, in_progress, completed, rejected
    assigned_to: Optional[str] = None  # Cline, Гефест, или другой агент
    handover_task_id: Optional[str] = None
    rejection_reason: Optional[str] = None


class HealthResponse(BaseModel):
    """Ответ healthcheck"""
    status: str
    version: str
    dependencies: Dict[str, str]
    uptime_seconds: float


class ApproveRequest(BaseModel):
    comment: Optional[str] = None

class RejectRequest(BaseModel):
    reason: str

class ApproveResponse(BaseModel):
    status: str
    handover_task_id: str

class RejectResponse(BaseModel):
    status: str
    reason: str


class HintsRequest(BaseModel):
    """Запрос на генерацию подсказок для нового проекта"""
    project_id: str
    initial_message: str
