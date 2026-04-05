from pydantic import BaseModel
from typing import Optional, List

class CommitRequest(BaseModel):
    content: dict
    message: str

class CommitResponse(BaseModel):
    commit_hash: str

class HistoryEntry(BaseModel):
    hash: str
    author: str
    date: str
    message: str
