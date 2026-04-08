import os
import json
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

PROJECT_MEMORY_URL = os.getenv("PROJECT_MEMORY_URL", "http://project-memory:8108")
C12_URL = os.getenv("C12_URL", "http://c1.2:8085")
SKILL_INTEGRATOR_URL = os.getenv("SKILL_INTEGRATOR_URL", "http://skill-integrator:8090")
HANDOVER_URL = os.getenv("HANDOVER_URL", "http://handover:8080")
DECOMPOSER_URL = os.getenv("DECOMPOSER_URL", "http://patch-architect:8085")
INTEGRATOR_URL = os.getenv("INTEGRATOR_URL", "http://integrator:8096")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


async def send_log_to_br18(event_type: str, details: dict):
    """Отправляет лог в BR18 (Log Aggregator)."""
    BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
    log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "C9.4", "event_type": event_type, "details": details}
    try:
        await client.post(BR18_URL, json=log_entry)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")


async def save_message_to_project(project_id: str, role: str, content: str, message_type: str = "text"):
    """Сохраняет сообщение в C2.6 (Project Memory)."""
    try:
        resp = await client.post(f"{PROJECT_MEMORY_URL}/projects/{project_id}/messages",
                                 json={"role": role, "content": content, "message_type": message_type}, timeout=5.0)
        resp.raise_for_status()
        logger.info(f"Message saved to project {project_id}")
    except Exception as e:
        logger.error(f"Failed to save message to project {project_id}: {e}")


async def _save_message(project_id: str, role: str, content: str):
    """Сохраняет сообщение в C2.6 через POST /projects/{id}/messages."""
    await save_message_to_project(project_id, role, content, "text")


async def _save_artifact(project_id: str, artifact_type: str, content: dict):
    """Сохраняет L2 через POST /projects/{id}/artifacts."""
    url = f"{PROJECT_MEMORY_URL}/projects/{project_id}/artifacts"
    payload = {
        "artifact_type": artifact_type,
        "name": f"L2_{artifact_type}",
        "content": json.dumps(content, ensure_ascii=False),
        "version": "1.0"
    }
    
    print(f"DEBUG _save_artifact: url={url}, payload keys={list(payload.keys())}")
    logger.info(f"Saving artifact to {url}, payload: {payload}")
    
    try:
        resp = await client.post(url, json=payload, timeout=5.0)
        print(f"DEBUG _save_artifact: response status={resp.status_code}, text={resp.text}")
        logger.info(f"Artifact save response: {resp.status_code} {resp.text}")
        resp.raise_for_status()
        logger.info(f"Artifact saved to project {project_id}, type: {artifact_type}")
        await send_log_to_br18("artifact_saved", {"project_id": project_id, "artifact_type": artifact_type})
    except Exception as e:
        print(f"DEBUG _save_artifact: exception {e}")
        logger.error(f"Failed to save artifact: {e}")
        await send_log_to_br18("artifact_save_failed", {"project_id": project_id, "artifact_type": artifact_type, "error": str(e)})
        raise


async def _call_c12(project_id: str, l2: dict):
    """Вызывает C1.2 через POST /decompose с телом {"project_id": project_id, "l2": l2}."""
    url = f"{C12_URL}/decompose"
    payload = {
        "description": json.dumps(l2, ensure_ascii=False),
        "context": {"project_id": project_id}
    }
    
    logger.info(f"Calling C1.2 at {url} with payload: {payload}")
    
    try:
        resp = await client.post(url, json=payload, timeout=30.0)
        logger.info(f"C1.2 response: {resp.status_code} {resp.text}")
        resp.raise_for_status()
        data = resp.json()
        patches = data.get("patches", [])
        logger.info(f"C1.2 called successfully, returned {len(patches)} patches")
        await send_log_to_br18("c12_called", {"project_id": project_id, "patches_count": len(patches)})
        return patches
    except Exception as e:
        logger.error(f"Failed to call C1.2: {e}")
        await send_log_to_br18("c12_call_failed", {"project_id": project_id, "error": str(e)})
        raise


async def call_skill_integrator(task_type: str) -> Optional[dict]:
    """Вызывает C7.4 Skill Integrator для получения навыка.
    
    Args:
        task_type: Тип задачи (например, "discovery")
        
    Returns:
        Словарь с ответом C7.4 или None при ошибке
    """
    url = f"{SKILL_INTEGRATOR_URL}/compile"
    payload = {"task_type": task_type}
    
    try:
        logger.info(f"Calling skill integrator at {url} for task_type={task_type}")
        resp = await client.post(url, json=payload, timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        
        # Проверяем структуру ответа
        if isinstance(data, dict) and "prompt" in data:
            skill_id = data.get("skill_id", "unknown")
            logger.info(f"Successfully loaded skill {skill_id} from C7.4")
            await send_log_to_br18("skill_loaded", {"skill_id": skill_id, "task_type": task_type})
            return data
        else:
            logger.error(f"Invalid response structure from C7.4: {data}")
            await send_log_to_br18("skill_invalid_response", {"task_type": task_type, "response": str(data)[:200]})
            return None
            
    except httpx.TimeoutException:
        logger.error(f"Timeout calling C7.4 skill integrator for {task_type}")
        await send_log_to_br18("skill_timeout", {"task_type": task_type})
        return None
    except httpx.HTTPStatusError as e:
        logger.error(f"C7.4 returned HTTP error {e.response.status_code}: {e.response.text}")
        await send_log_to_br18("skill_http_error", {"task_type": task_type, "status": e.response.status_code})
        return None
    except Exception as e:
        logger.error(f"Error calling C7.4 skill integrator: {e}")
        await send_log_to_br18("skill_call_error", {"task_type": task_type, "error": str(e)})
        return None


async def call_decomposer(description: str, task_id: str) -> list:
    """Вызывает декомпозитор для разбиения задачи на патчи."""
    url = f"{DECOMPOSER_URL}/decompose"
    payload = {"description": description, "context": {"task_id": task_id}}
    try:
        resp = await client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("patches", [])
    except Exception as e:
        logger.error(f"Decomposer call failed: {e}")
        await send_log_to_br18("decomposition_failed", {"task_id": task_id, "error": str(e)})
        return []


async def call_integrator(patch_ids: list, task_id: str):
    """Вызывает интегратор для сборки патчей."""
    url = f"{INTEGRATOR_URL}/build"
    payload = {"task_id": task_id, "patch_ids": patch_ids, "check_skills": True, "run_tests": True}
    logger.info(f"Calling integrator at {url} with payload {payload}")
    try:
        resp = await client.post(url, json=payload, timeout=30.0)
        logger.info(f"Integrator response: {resp.status_code} {resp.text[:200]}")
        resp.raise_for_status()
        logger.info(f"Integrator triggered with {len(patch_ids)} patches for task {task_id}")
        await send_log_to_br18("integration_triggered", {"task_id": task_id, "patch_ids": patch_ids})
    except Exception as e:
        logger.error(f"Integrator call failed: {e}")
        await send_log_to_br18("integration_failed", {"task_id": task_id, "patch_ids": patch_ids, "error": str(e)})
