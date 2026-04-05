from pydantic import BaseModel, validator
from typing import Optional

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

class MessageCreate(BaseModel):
    role: str
    content: str
    message_type: str = "text"

    @validator('role')
    def role_valid(cls, v):
        if v not in ('user', 'assistant'):
            raise ValueError('role must be "user" or "assistant"')
        return v

    @validator('message_type')
    def type_valid(cls, v):
        if v not in ('text', 'command', 'decision'):
            raise ValueError('message_type must be one of: text, command, decision')
        return v

class MessageResponse(BaseModel):
    id: int
    project_id: str
    role: str
    content: str
    timestamp: str
    message_type: str

class ArtifactCreate(BaseModel):
    artifact_type: str
    name: str
    content: str
    version: Optional[str] = None

    @validator('artifact_type')
    def type_valid(cls, v):
        if v not in ('patch', 'specification', 'code', 'test'):
            raise ValueError('artifact_type must be one of: patch, specification, code, test')
        return v

class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    artifact_type: str
    name: str
    version: Optional[str] = None
    created_at: str

class SearchRequest(BaseModel):
    query: str
    n_results: int = 5

class SearchResult(BaseModel):
    score: float
    type: str
    id: str
    content: str
    metadata: dict

class SearchResponse(BaseModel):
    results: list[SearchResult]
# Глобальная индексация и поиск для завода
class IndexRequest(BaseModel):
    documents: list[str]   # пути к файлам

class IndexResponse(BaseModel):
    status: str
    indexed_count: int
    errors: list[str]

class GlobalSearchRequest(BaseModel):
    query: str
    limit: int = 5

class GlobalSearchResult(BaseModel):
    path: str
    score: float
    snippet: str
    metadata: dict

class GlobalSearchResponse(BaseModel):
    results: list[GlobalSearchResult]
