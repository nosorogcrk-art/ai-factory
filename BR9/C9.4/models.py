from pydantic import BaseModel, Field
from typing import Optional

class DialogRequest(BaseModel):
    project_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)

class DialogResponse(BaseModel):
    session_id: str
    reply: str
    completed: bool = False
    task_id: Optional[str] = None