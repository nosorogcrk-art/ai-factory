from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class PackageRequest(BaseModel):
    repo_path: str = Field(default="02_ПРОДУКТ/РЕПО")
    version: str = Field(default="")
    skills: List[str] = Field(default_factory=list)

class PackageResponse(BaseModel):
    status: str
    archive: str

class FileInfo(BaseModel):
    path: str
    content: str

class PackageCodeRequest(BaseModel):
    files: Optional[List[FileInfo]] = None
    source_dir: Optional[str] = None

class PackageCodeResponse(BaseModel):
    status: str
    artifact_url: str
    version: str
