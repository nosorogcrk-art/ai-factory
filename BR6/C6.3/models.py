from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class CostReport(BaseModel):
    agent: str
    task_id: Optional[str] = None
    branch: Optional[str] = None
    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    success: bool
    duration_ms: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class CheckRequest(BaseModel):
    agent: str
    model: str
    estimated_tokens: int = 0
    branch: Optional[str] = None
    task_id: Optional[str] = None
