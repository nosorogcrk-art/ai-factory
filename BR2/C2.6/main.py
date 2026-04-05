"""FastAPI приложение Project Memory."""
import threading
import os
import logging
import httpx
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import services
import models

app = FastAPI(title="Project Memory", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/project_memory.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks):
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "C2.6",
        "event_type": event_type,
        "details": details
    }

    async def _send():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(BR18_URL, json=log_entry, timeout=2.0)
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")

    background_tasks.add_task(_send)


@app.on_event("startup")
def startup():
    services.recover_projects()
    threading.Thread(target=services.reindex_all_projects, daemon=True).start()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/projects", status_code=201, response_model=models.ProjectResponse)
async def create_project(req: models.ProjectCreate, background_tasks: BackgroundTasks):
    try:
        result = services.create_project_service(req.name, req.description)
        await send_log_to_br18("project_created", {
            "project_id": result["id"],
            "name": result["name"],
            "description": result["description"]
        }, background_tasks)
        return result
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@app.get("/projects", response_model=list[models.ProjectResponse])
async def list_projects(include_archived: bool = False, limit: int = 100, offset: int = 0):
    return services.list_projects_service(include_archived, limit, offset)


@app.get("/projects/{project_id}", response_model=models.ProjectResponse)
async def get_project(project_id: str, include_archived: bool = False):
    return services.get_project_service(project_id, include_archived)


@app.patch("/projects/{project_id}", response_model=models.ProjectResponse)
async def update_project(project_id: str, req: models.ProjectUpdate, background_tasks: BackgroundTasks):
    result = services.update_project_service(project_id, req.name, req.description)
    await send_log_to_br18("project_updated", {
        "project_id": project_id,
        "name": result.name,
        "description": result.description
    }, background_tasks)
    return result


@app.delete("/projects/{project_id}", status_code=204)
async def delete_project(project_id: str, background_tasks: BackgroundTasks):
    services.delete_project_service(project_id)
    await send_log_to_br18("project_deleted", {"project_id": project_id}, background_tasks)
    return None


@app.post("/projects/{project_id}/messages", status_code=201, response_model=models.MessageResponse)
async def add_message(project_id: str, msg: models.MessageCreate, background_tasks: BackgroundTasks):
    result = services.add_message_service(project_id, msg.role, msg.content, msg.message_type)
    await send_log_to_br18("message_added", {
        "project_id": project_id,
        "message_id": result["id"],
        "role": msg.role,
        "content_preview": msg.content[:100]
    }, background_tasks)
    return models.MessageResponse(
        id=result["id"],
        project_id=project_id,
        role=msg.role,
        content=msg.content,
        timestamp=result["timestamp"],
        message_type=msg.message_type
    )


@app.get("/projects/{project_id}/messages", response_model=list[models.MessageResponse])
async def get_messages(project_id: str, limit: int = 100, offset: int = 0, since: str = None):
    return services.get_messages_service(project_id, limit, offset, since)


@app.post("/projects/{project_id}/artifacts", status_code=201, response_model=models.ArtifactResponse)
async def add_artifact(project_id: str, artifact: models.ArtifactCreate, background_tasks: BackgroundTasks):
    result = services.add_artifact_service(
        project_id, artifact.artifact_type, artifact.name, artifact.content, artifact.version
    )
    await send_log_to_br18("artifact_added", {
        "project_id": project_id,
        "artifact_id": result["id"],
        "artifact_type": artifact.artifact_type,
        "name": artifact.name
    }, background_tasks)
    return models.ArtifactResponse(
        id=result["id"],
        project_id=result["project_id"],
        artifact_type=result["artifact_type"],
        name=result["name"],
        version=result["version"],
        created_at=result["created_at"]
    )


@app.get("/projects/{project_id}/artifacts", response_model=list[models.ArtifactResponse])
async def list_artifacts(project_id: str, artifact_type: str = None, limit: int = 100, offset: int = 0):
    return services.list_artifacts_service(project_id, artifact_type, limit, offset)


@app.get("/projects/{project_id}/artifacts/{artifact_id}", response_model=models.ArtifactResponse)
async def get_artifact_metadata(project_id: str, artifact_id: str):
    return services.get_artifact_metadata_service(project_id, artifact_id)


@app.get("/projects/{project_id}/artifacts/{artifact_id}/content")
async def get_artifact_content(project_id: str, artifact_id: str):
    content = services.get_artifact_content_service(project_id, artifact_id)
    return {"content": content}


@app.delete("/projects/{project_id}/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(project_id: str, artifact_id: str, background_tasks: BackgroundTasks):
    services.delete_artifact_service(project_id, artifact_id)
    await send_log_to_br18("artifact_deleted", {
        "project_id": project_id,
        "artifact_id": artifact_id
    }, background_tasks)
    return None


@app.post("/projects/{project_id}/search", response_model=models.SearchResponse)
async def search_project(project_id: str, req: models.SearchRequest, background_tasks: BackgroundTasks):
    results = services.search_project_service(project_id, req.query, req.n_results)
    await send_log_to_br18("search_performed", {
        "project_id": project_id,
        "query": req.query,
        "results_count": len(results)
    }, background_tasks)
    return models.SearchResponse(results=results)


@app.post("/index", response_model=models.IndexResponse)
async def global_index(req: models.IndexRequest, background_tasks: BackgroundTasks):
    indexed, errors = services.index_documents(req.documents)
    await send_log_to_br18("global_index", {
        "documents": req.documents,
        "indexed_count": indexed,
        "errors": errors
    }, background_tasks)
    return models.IndexResponse(status="ok", indexed_count=indexed, errors=errors)

@app.post("/search", response_model=models.GlobalSearchResponse)
async def global_search(req: models.GlobalSearchRequest, background_tasks: BackgroundTasks):
    results = services.search_factory(req.query, req.limit)
    await send_log_to_br18("global_search", {"query": req.query, "results_count": len(results)}, background_tasks)
    return models.GlobalSearchResponse(results=[
        models.GlobalSearchResult(**r) for r in results
    ])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8108)