from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class DecomposeRequest(BaseModel):
    description: str = Field(..., min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)


class BranchDesign(BaseModel):
    id: str
    name: str
    description: str
    containers: List[str] = Field(default_factory=list)


class DecomposeResponse(BaseModel):
    patches: List[str]
    branches: Optional[List[BranchDesign]] = None
    status: str = "ok"
