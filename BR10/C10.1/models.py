from pydantic import BaseModel
from typing import List, Optional


class BuildRequest(BaseModel):
    task_id: str
    patch_ids: List[str]
    check_skills: bool = True
    run_tests: bool = False


class BuildResponse(BaseModel):
    status: str
    message: str


class GenerateRequest(BaseModel):
    spec_path: str
    spec_content: Optional[str] = None


class GenerateResponse(BaseModel):
    status: str  # "generated" | "error"
    message: str
    files: List[str]
