from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class MetricIn(BaseModel):
    name: str
    value: float
    timestamp: datetime
    source: str
    tags: Optional[Dict[str, Any]] = None

class MetricAggregate(BaseModel):
    mean: float
    max: float
    min: float
    sum: float
    p95: Optional[float] = None
    last_update: datetime

class MetricHistoryItem(BaseModel):
    timestamp: datetime
    value: float
