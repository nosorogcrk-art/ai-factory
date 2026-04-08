from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Violation(BaseModel):
    rule: str
    message: str
    severity: Severity


class ReviewRequest(BaseModel):
    file_path: str
    content: Optional[str] = None


class ReviewResponse(BaseModel):
    status: str  # "approved" | "rework"
    violations: List[Violation]
    suggestions: List[str]


class HealthResponse(BaseModel):
    status: str