from pydantic import BaseModel, Field
from typing import List

class PackageRequest(BaseModel):
    repo_path: str = Field(default="02_ПРОДУКТ/РЕПО")
    version: str = Field(default="")
    skills: List[str] = Field(default_factory=list)

class PackageResponse(BaseModel):
    status: str
    archive: str