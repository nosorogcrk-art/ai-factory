"""
Pydantic модели для тестирования конфигураций
"""

from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class TestType(str, Enum):
    """Типы тестов"""
    SYNTAX = "syntax"
    SEMANTIC = "semantic"
    FUNCTIONAL = "functional"
    REGRESSION = "regression"


class TestStatus(str, Enum):
    """Статусы тестов"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class TestRequest(BaseModel):
    """Запрос на запуск тестов"""
    repo: str = Field(..., description="Название репозитория")
    commit: str = Field(..., description="Хэш коммита")
    tests: List[TestType] = Field(
        default=[TestType.SYNTAX, TestType.SEMANTIC],
        description="Список типов тестов для запуска"
    )
    environment: Optional[str] = Field(
        default="staging",
        description="Окружение для тестирования"
    )


class TestResult(BaseModel):
    """Результат одного теста"""
    test_type: TestType
    passed: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    duration_ms: Optional[int] = None


class TestResponse(BaseModel):
    """Ответ на запуск тестов"""
    test_id: str
    status: TestStatus
    created_at: datetime
    repo: str
    commit: str
    tests: List[TestType]


class TestResultsResponse(BaseModel):
    """Полные результаты тестов"""
    test_id: str
    status: TestStatus
    passed: bool
    results: Dict[TestType, TestResult]
    created_at: datetime
    completed_at: Optional[datetime] = None


class HealthResponse(BaseModel):
    """Ответ на проверку здоровья"""
    status: str
    timestamp: datetime
    version: str = "1.0"


class SyntaxTestResult(BaseModel):
    """Результат синтаксического теста"""
    file_path: str
    valid: bool
    errors: List[str] = Field(default_factory=list)


class SemanticTestResult(BaseModel):
    """Результат семантического теста"""
    file_path: str
    valid: bool
    missing_references: List[str] = Field(default_factory=list)
    duplicate_ids: List[str] = Field(default_factory=list)


class FunctionalTestResult(BaseModel):
    """Результат функционального теста"""
    test_name: str
    passed: bool
    output: Optional[str] = None
    error: Optional[str] = None