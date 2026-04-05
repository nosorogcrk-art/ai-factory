from pydantic import BaseModel
from typing import List


class BuildRequest(BaseModel):
    task_id: str
    patch_ids: List[str]
    check_skills: bool = True
    run_tests: bool = False


class BuildResponse(BaseModel):
    status: str
    message: str