from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict
from datetime import datetime

class BranchBase(BaseModel):
    name: str
    endpoint: str
    status: str = Field("active", pattern="^(active|inactive|maintenance)$")
    version: str = "0.1.0"
    containers: List[str] = []
    metadata: Dict[str, str] = {}

    @validator("endpoint")
    def validate_endpoint(cls, v):
        if not v.startswith(("http://", "https://")):
            raise ValueError("Endpoint must start with http:// or https://")
        return v

class BranchCreate(BranchBase):
    pass

class BranchUpdate(BaseModel):
    name: Optional[str] = None
    endpoint: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None
    containers: Optional[List[str]] = None
    metadata: Optional[Dict[str, str]] = None

    @validator("endpoint")
    def validate_endpoint(cls, v):
        if v is not None and not v.startswith(("http://", "https://")):
            raise ValueError("Endpoint must start with http:// or https://")
        return v

class BranchInDB(BranchBase):
    id: str
    created_at: datetime
    updated_at: datetime
    soft_deleted: bool = False
