from pydantic import BaseModel
from typing import List, Optional, Dict, Any


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


class FileItem(BaseModel):
    path: str
    content: str


class GenerateFromL5Request(BaseModel):
    container_id: str
    spec: Dict[str, Any]


class GenerateFromL5Response(BaseModel):
    status: str  # "success" | "error"
    files: List[FileItem]
