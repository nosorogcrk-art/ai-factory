"""Бизнес-логика Project Memory."""
import os
import json
import uuid
import logging
import requests
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from datetime import datetime, timezone
from fastapi import HTTPException
from typing import Optional, List

import repositories as repo
import models

logger = logging.getLogger(__name__)

PROJECTS_ROOT = Path("01_ЦЕХ/ПРОЕКТЫ")
CHROMA_PATH = PROJECTS_ROOT / "chroma_data"
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "5"))
MAX_ARTIFACT_SIZE = int(os.getenv("MAX_ARTIFACT_SIZE", 10 * 1024 * 1024))
MAX_LIMIT = 500

CHROMA_PATH.mkdir(parents=True, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=str(CHROMA_PATH))
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="all-MiniLM-L6-v2"
)

def get_project_collection(project_id: str):
    collection_name = f"project_{project_id}".replace("-", "_")
    try:
        return chroma_client.get_collection(name=collection_name)
    except ValueError:
        return chroma_client.create_collection(
            name=collection_name, embedding_function=embedding_fn
        )

def get_factory_collection():
    try:
        return chroma_client.get_collection(name="factory_docs")
    except (ValueError, chromadb.errors.NotFoundError):
        return chroma_client.create_collection(
            name="factory_docs", embedding_function=embedding_fn
        )

def add_to_chroma(project_id: str, doc_id: str, text: str, doc_type: str, metadata: dict):
    try:
        collection = get_project_collection(project_id)
        collection.add(documents=[text], metadatas=[metadata], ids=[doc_id])
        logger.info(f"Added to Chroma: {doc_id} for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to add to Chroma: {e}")

def delete_from_chroma(project_id: str, doc_id: str):
    try:
        collection = get_project_collection(project_id)
        collection.delete(ids=[doc_id])
        logger.info(f"Deleted from Chroma: {doc_id} for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to delete from Chroma: {e}")

def index_document(file_path: str) -> tuple[bool, str]:
    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}"
    if path.stat().st_size > 10 * 1024 * 1024:
        return False, f"File too large: {file_path}"
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, f"Failed to read file: {e}"
    
    import hashlib
    doc_id = f"file_{hashlib.sha256(str(path).encode()).hexdigest()[:16]}"
    
    ext = path.suffix.lower()
    if ext == '.md':
        doc_type = 'markdown'
    elif ext == '.json':
        doc_type = 'json'
    elif ext == '.py':
        doc_type = 'code'
    else:
        doc_type = 'unknown'
    
    metadata = {
        "path": str(path),
        "filename": path.name,
        "size": path.stat().st_size,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": doc_type
    }
    
    collection = get_factory_collection()
    try:
        collection.add(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.info(f"Indexed: {file_path}")
        return True, ""
    except Exception as e:
        return False, f"Chroma error: {e}"

def index_documents(doc_paths: list[str]) -> tuple[int, list[str]]:
    indexed = 0
    errors = []
    for path in doc_paths:
        ok, err = index_document(path)
        if ok:
            indexed += 1
        else:
            errors.append(err)
    return indexed, errors

def search_factory(query: str, limit: int = 5) -> list[dict]:
    try:
        collection = get_factory_collection()
        results = collection.query(
            query_texts=[query],
            n_results=limit,
            include=["documents", "metadatas", "distances"]
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return []
    
    out = []
    if results["ids"] and len(results["ids"][0]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            score = 1 - results["distances"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            document = results["documents"][0][i] if results["documents"] else ""
            out.append({
                "path": metadata.get("path", ""),
                "score": float(score),
                "snippet": document[:200],
                "metadata": metadata
            })
    return out

def reindex_project(project_id: str):
    conn = repo.get_connection()
    cur = conn.cursor()
    try:
        collection = get_project_collection(project_id)
        existing_ids = set(collection.get()["ids"]) if collection.count() > 0 else set()
    except Exception as e:
        logger.error(f"Cannot get collection for {project_id}: {e}")
        conn.close()
        return

    cur.execute("SELECT id, role, content, timestamp FROM project_messages WHERE project_id = ?", (project_id,))
    for row in cur.fetchall():
        msg_id, role, content, ts = row
        doc_id = f"msg_{msg_id}"
        if doc_id in existing_ids:
            continue
        metadata = {"type": "message", "message_id": msg_id, "project_id": project_id, "role": role, "timestamp": ts}
        add_to_chroma(project_id, doc_id, content, "message", metadata)

    cur.execute("SELECT id, artifact_type, name, version FROM project_artifacts WHERE project_id = ?", (project_id,))
    for row in cur.fetchall():
        art_id, art_type, name, version = row
        doc_id = f"art_{art_id}"
        if doc_id in existing_ids:
            continue
        file_path = repo.get_artifact_file_path(project_id, art_id)
        if not file_path.exists():
            logger.warning(f"Artifact file missing for {art_id}")
            continue
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Failed to read artifact {art_id}: {e}")
            continue
        metadata = {"type": "artifact", "artifact_id": art_id, "artifact_type": art_type, "name": name, "version": version if version else ""}
        add_to_chroma(project_id, doc_id, content, "artifact", metadata)
    conn.close()

def reindex_all_projects():
    conn = repo.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM projects WHERE status = 'active'")
    projects = cur.fetchall()
    conn.close()
    for (project_id,) in projects:
        reindex_project(project_id)
    logger.info("Reindexing completed")

def send_log_sync(event_type: str, details: dict):
    try:
        log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "C2.6", "event_type": event_type, "details": details}
        requests.post(BR18_URL, json=log_entry, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

def create_metadata_file(project_id: str, name: str, description: str = None, status: str = "active"):
    try:
        project_dir = PROJECTS_ROOT / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        metadata = {"id": project_id, "name": name, "description": description, "status": status,
                    "created_at": datetime.now(timezone.utc).isoformat(), "updated_at": datetime.now(timezone.utc).isoformat()}
        with open(project_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Metadata file created for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to create metadata for {project_id}: {e}")
        raise

def update_metadata_file(project_id: str, name: str = None, description: str = None, status: str = None):
    try:
        project_dir = PROJECTS_ROOT / project_id
        if not project_dir.exists():
            return
        metadata_path = project_dir / "metadata.json"
        if not metadata_path.exists():
            metadata = {}
        else:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        if name is not None:
            metadata["name"] = name
        if description is not None:
            metadata["description"] = description
        if status is not None:
            metadata["status"] = status
        metadata["updated_at"] = datetime.now(timezone.utc).isoformat()
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        logger.info(f"Metadata file updated for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to update metadata for {project_id}: {e}")

def ensure_project_dir(project_id: str) -> bool:
    return (PROJECTS_ROOT / project_id).exists()

def recover_projects():
    conn = repo.get_connection()
    cur = conn.cursor()
    try:
        for project_dir in PROJECTS_ROOT.iterdir():
            if not project_dir.is_dir():
                continue
            project_id = project_dir.name
            metadata_path = project_dir / "metadata.json"
            if not metadata_path.exists():
                continue
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except Exception as e:
                logger.error(f"Error reading metadata for {project_id}: {e}")
                continue
            if not repo.project_exists(project_id):
                repo.recover_project_from_metadata(project_id, metadata)
                logger.info(f"Recovered project {project_id} from filesystem")

        for project_dir in PROJECTS_ROOT.iterdir():
            if not project_dir.is_dir():
                continue
            project_id = project_dir.name
            artifacts_dir = project_dir / "artifacts"
            if not artifacts_dir.exists():
                continue
            for file_path in artifacts_dir.iterdir():
                if not file_path.is_file():
                    continue
                if not file_path.name.startswith("art_") or not file_path.name.endswith(".txt"):
                    continue
                artifact_id = file_path.stem
                if repo.get_artifact_metadata(artifact_id) is None:
                    repo.recover_artifact(artifact_id, project_id, file_path.name)
                    logger.info(f"Recovered artifact {artifact_id} for project {project_id}")
    except Exception as e:
        logger.error(f"Error during project recovery: {e}")
    finally:
        conn.close()

def create_project_service(name: str, description: Optional[str]) -> dict:
    if repo.name_exists_active(name):
        raise ValueError("Project with this name already exists")
    project_id = f"proj_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    repo.create_project(project_id, name, description, now)
    try:
        create_metadata_file(project_id, name, description, "active")
    except Exception:
        with repo.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
        raise
    send_log_sync("project_created", {"project_id": project_id, "name": name, "description": description})
    return {"id": project_id, "name": name, "description": description, "status": "active", "created_at": now, "updated_at": now}

def list_projects_service(include_archived: bool, limit: int, offset: int) -> List[models.ProjectResponse]:
    limit = min(limit, MAX_LIMIT)
    rows = repo.get_all_projects(limit, offset) if include_archived else repo.get_active_projects(limit, offset)
    return [models.ProjectResponse(id=r[0], name=r[1], description=r[2], status=r[3], created_at=r[4], updated_at=r[5]) for r in rows]

def get_project_service(project_id: str, include_archived: bool) -> models.ProjectResponse:
    row = repo.get_project_by_id(project_id)
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")
    if not include_archived and row[3] == "archived":
        raise HTTPException(status_code=404, detail="Project not found")
    return models.ProjectResponse(id=row[0], name=row[1], description=row[2], status=row[3], created_at=row[4], updated_at=row[5])

def update_project_service(project_id: str, name: Optional[str], description: Optional[str]) -> models.ProjectResponse:
    current = repo.get_project_by_id(project_id)
    if not current:
        raise HTTPException(status_code=404, detail="Project not found")
    if name is not None and name != current[1]:
        if repo.name_exists_other_active(name, project_id):
            raise HTTPException(status_code=409, detail="Project with this name already exists")
    updated_at = datetime.now(timezone.utc).isoformat()
    repo.update_project(project_id, name, description, updated_at)
    update_metadata_file(project_id, name=name, description=description)
    send_log_sync("project_updated", {"project_id": project_id, "name": name, "description": description})
    return models.ProjectResponse(id=current[0], name=name if name is not None else current[1],
                                  description=description if description is not None else current[2],
                                  status=current[3], created_at=current[4], updated_at=updated_at)

def delete_project_service(project_id: str):
    status = repo.get_project_status(project_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if status == "archived":
        raise HTTPException(status_code=400, detail="Project already archived")
    updated_at = datetime.now(timezone.utc).isoformat()
    repo.delete_project(project_id, updated_at)
    update_metadata_file(project_id, status="archived")
    send_log_sync("project_deleted", {"project_id": project_id})

def add_message_service(project_id: str, role: str, content: str, message_type: str) -> dict:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not ensure_project_dir(project_id):
        raise HTTPException(status_code=500, detail="Project directory missing")
    timestamp = datetime.now(timezone.utc).isoformat()
    message_id = repo.insert_message(project_id, role, content, message_type, timestamp)
    doc_id = f"msg_{message_id}"
    metadata = {"type": "message", "message_id": message_id, "project_id": project_id, "role": role, "timestamp": timestamp}
    add_to_chroma(project_id, doc_id, content, "message", metadata)
    send_log_sync("message_added", {"project_id": project_id, "message_id": message_id, "role": role})
    return {"id": message_id, "timestamp": timestamp}

def get_messages_service(project_id: str, limit: int, offset: int, since: Optional[str]) -> List[models.MessageResponse]:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if since:
        try:
            datetime.fromisoformat(since)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid since format (ISO 8601 expected)")
    limit = min(limit, MAX_LIMIT)
    rows = repo.get_project_messages(project_id, limit, offset, since)
    return [models.MessageResponse(id=r[0], project_id=r[1], role=r[2], content=r[3], timestamp=r[4], message_type=r[5]) for r in rows]

def add_artifact_service(project_id: str, artifact_type: str, name: str, content: str, version: Optional[str]) -> dict:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    if not ensure_project_dir(project_id):
        raise HTTPException(status_code=500, detail="Project directory missing")
    if len(content) > MAX_ARTIFACT_SIZE:
        raise HTTPException(status_code=413, detail="Artifact content too large")
    artifact_id = f"art_{uuid.uuid4().hex[:8]}"
    filename = f"{artifact_id}.txt"
    artifact_path = PROJECTS_ROOT / project_id / "artifacts" / filename
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()
    try:
        repo.insert_artifact(artifact_id, project_id, artifact_type, name, filename, version, now)
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to create artifact: {e}")
        raise HTTPException(status_code=500, detail="Failed to save artifact")
    doc_id = f"art_{artifact_id}"
    metadata = {"type": "artifact", "artifact_id": artifact_id, "artifact_type": artifact_type, "name": name, "version": version if version else ""}
    add_to_chroma(project_id, doc_id, content, "artifact", metadata)
    send_log_sync("artifact_added", {"project_id": project_id, "artifact_id": artifact_id, "artifact_type": artifact_type, "name": name})
    return {"id": artifact_id, "project_id": project_id, "artifact_type": artifact_type, "name": name, "version": version, "created_at": now}

def list_artifacts_service(project_id: str, artifact_type: Optional[str], limit: int, offset: int) -> List[models.ArtifactResponse]:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    limit = min(limit, MAX_LIMIT)
    rows = repo.get_artifacts_by_project(project_id, artifact_type, limit, offset)
    return [models.ArtifactResponse(id=r[0], project_id=r[1], artifact_type=r[2], name=r[3], version=r[4], created_at=r[5]) for r in rows]

def get_artifact_metadata_service(project_id: str, artifact_id: str) -> models.ArtifactResponse:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    row = repo.get_artifact_metadata(artifact_id)
    if not row or row[1] != project_id:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return models.ArtifactResponse(id=row[0], project_id=row[1], artifact_type=row[2], name=row[3], version=row[4], created_at=row[5])

def get_artifact_content_service(project_id: str, artifact_id: str) -> str:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    filename = repo.get_artifact_filename(artifact_id)
    if not filename:
        raise HTTPException(status_code=404, detail="Artifact not found")
    file_path = repo.get_artifact_file_path(project_id, artifact_id)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artifact file not found")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to read artifact file {file_path}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read artifact")

def delete_artifact_service(project_id: str, artifact_id: str):
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    filename = repo.get_artifact_filename(artifact_id)
    if not filename:
        raise HTTPException(status_code=404, detail="Artifact not found")
    repo.delete_artifact(artifact_id)
    file_path = repo.get_artifact_file_path(project_id, artifact_id)
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.error(f"Failed to delete artifact file {file_path}: {e}")
    delete_from_chroma(project_id, f"art_{artifact_id}")
    send_log_sync("artifact_deleted", {"project_id": project_id, "artifact_id": artifact_id})

def search_project_service(project_id: str, query: str, n_results: int) -> List[models.SearchResult]:
    if not repo.project_exists(project_id):
        raise HTTPException(status_code=404, detail="Project not found")
    try:
        collection = get_project_collection(project_id)
        results = collection.query(query_texts=[query], n_results=n_results, include=["documents", "metadatas", "distances"])
    except Exception as e:
        logger.error(f"Chroma query failed: {e}")
        raise HTTPException(status_code=503, detail="Search service unavailable")
    out = []
    if results["ids"] and len(results["ids"][0]) > 0:
        for i, doc_id in enumerate(results["ids"][0]):
            score = 1 - results["distances"][0][i]
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            out.append(models.SearchResult(score=float(score), type=metadata.get("type", "unknown"), id=doc_id, content=results["documents"][0][i], metadata=metadata))
    return out
