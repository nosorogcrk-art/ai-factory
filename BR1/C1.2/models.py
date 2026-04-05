from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class DecomposeRequest(BaseModel):
    description: str = Field(..., min_length=1)
    context: Dict[str, Any] = Field(default_factory=dict)


class DecomposeResponse(BaseModel):
    patches: list[str]
    status: str = "ok"