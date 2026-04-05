from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re

class SkillBase(BaseModel):
    name: str
    version: str
    description: str
    author: str
    status: str = Field("draft", pattern="^(draft|active|deprecated|deleted)$")
    tags: List[str] = []
    task_types: List[str] = []
    languages: List[str] = []
    allowed_for_swarm: bool = False
    depends_on: List[str] = []
    related_patches: List[str] = []
    instruction: str

    @field_validator("version")
    def validate_version(cls, v):
        pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$'
        if not re.match(pattern, v):
            raise ValueError('Version must be in semver format (e.g., 1.2.3)')
        return v

class SkillCreate(SkillBase):
    pass

class SkillUpdate(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None
    task_types: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    allowed_for_swarm: Optional[bool] = None
    depends_on: Optional[List[str]] = None
    related_patches: Optional[List[str]] = None
    instruction: Optional[str] = None

    @field_validator("version")
    def validate_version(cls, v):
        if v is not None:
            pattern = r'^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$'
            if not re.match(pattern, v):
                raise ValueError('Version must be in semver format')
        return v

class SkillInDB(SkillBase):
    id: str
    created_at: datetime
    updated_at: datetime
    soft_deleted: bool = False