from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class SkillMetadata(BaseModel):
    id: str
    name: str
    version: str
    description: str
    author: str
    status: str
    tags: List[str] = []
    task_types: List[str] = []
    languages: List[str] = []
    allowed_for_swarm: bool = False
    depends_on: List[str] = []
    related_patches: List[str] = []
    instruction: str
    created_at: datetime
    updated_at: datetime

class SkillResponse(BaseModel):
    id: str
    version: str
    name: str
    instruction: str
    dependencies: List[str]
    metadata: Dict[str, Any]

class BatchRequest(BaseModel):
    skills: List[str]
    agent_type: str = "main"

class StatusResponse(BaseModel):
    status: str
    cache_stats: Dict[str, int]