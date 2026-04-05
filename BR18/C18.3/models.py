from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

class RuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    condition: str          # например "cpu_usage > 90"
    channels: List[str]     # ["telegram", "slack"]
    cooldown_minutes: int = 60

class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    condition: Optional[str] = None
    channels: Optional[List[str]] = None
    cooldown_minutes: Optional[int] = None

class RuleInDB(RuleCreate):
    id: str
    created_at: datetime
    updated_at: datetime

class AlertEvent(BaseModel):
    rule_id: str
    rule_name: str
    condition: str
    value: float
    threshold: float
    channels: List[str]
    timestamp: datetime
    success: bool = True
    error: Optional[str] = None
