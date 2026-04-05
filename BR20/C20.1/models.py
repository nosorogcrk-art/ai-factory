from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class DeployRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    version: Optional[str] = None

class Deployment(BaseModel):
    id: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    repo_url: str
    branch: str
    version: Optional[str] = None
    log: Optional[str] = None

class WebhookPayload(BaseModel):
    ref: str
    repository: dict