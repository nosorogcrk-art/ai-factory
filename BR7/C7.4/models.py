from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class CompileRequest(BaseModel):
    task_type: str
    agent_type: str = "main"
    language: Optional[str] = None
    context: Optional[str] = None
    required_skills: Optional[List[str]] = None
    limit: int = 5
    budget: Optional[int] = None  # добавлено для полноты

class CompileResponse(BaseModel):
    prompt: str
    used_skills: List[str]
    warnings: List[str] = []
    total_matched: int
    returned: int

class ExecuteRequest(BaseModel):
    task_type: str
    context: Dict[str, Any]  # произвольный JSON, который будет передан в LLM

class ExecuteResponse(BaseModel):
    result: Dict[str, Any]   # JSON-ответ от LLM
    skill_id: str
    warnings: List[str] = []
