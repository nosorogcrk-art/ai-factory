"""Pydantic models for Skill Tester."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class TestRequest(BaseModel):
    """Request to test a skill."""
    skill_id: str
    test_case: Optional[str] = None

class TestRunResponse(BaseModel):
    """Response when a test is started (or completed)."""
    test_run_id: str
    skill_id: str
    status: str  # "in_progress" or "completed"
    passed: Optional[bool] = None
    output: Optional[str] = None
    duration_seconds: Optional[float] = None

class TestResult(BaseModel):
    """Individual test case result."""
    name: str
    passed: bool
    duration_ms: int
    error: Optional[str] = None
    actual_output: Optional[str] = None

class SkillTestResults(BaseModel):
    """Full results for a skill."""
    skill_id: str
    last_test: Optional[datetime] = None
    overall: str  # "passed" or "failed"
    tests: List[TestResult]
    metrics: Optional[Dict[str, Any]] = None  # обязательно для P17.4.4