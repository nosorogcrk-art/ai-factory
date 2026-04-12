import json
import uuid
import logging
from typing import Optional, Tuple
import repositories as repo
from external_api import (
    _save_artifact, _call_c12, send_log_to_br18, 
    call_decomposer, call_integrator, PROJECT_MEMORY_URL,
    HANDOVER_URL
)
import services

logger = logging.getLogger(__name__)


async def create_task_in_registry(description: dict, project_id: str) -> Optional[str]:
    """Создаёт задачу в реестре задач (Handover)."""
    import httpx
    client = httpx.AsyncClient(timeout=5.0)
    
    task_id = f"DIALOG-{uuid.uuid4().hex[:8]}"
    payload = {"task_id": task_id, "actor": "АРХИ", "comment": json.dumps(description, ensure_ascii=False), "project_id": project_id}
    try:
        resp = await client.post(f"{HANDOVER_URL}/take", json=payload, timeout=5.0)
        if resp.status_code == 200:
            logger.info(f"Task created: {task_id}")
            await send_log_to_br18("task_created", {"task_id": task_id, "source": "dialogue"})
            return task_id
        else:
            logger.error(f"Failed to create task: {resp.status_code} - {resp.text}")
            await send_log_to_br18("task_create_failed", {"status": resp.status_code, "error": resp.text})
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        await send_log_to_br18("task_create_error", {"error": str(e)})
    return None


async def _process_l2_response(project_id: str, l2_data: dict, collected: dict) -> Tuple[str, bool, Optional[str], Optional[dict]]:
    """Обрабатывает L2 ответ: сохраняет артефакт, вызывает C1.2, создаёт задачу."""
    try:
        print(f"DEBUG _process_l2_response: starting for project {project_id}")
        logger.info(f"Saving artifact for project {project_id}, L2 keys: {list(l2_data.keys())}")
        await _save_artifact(project_id, "specification", l2_data)
        print("DEBUG _process_l2_response: artifact saved")
        logger.info(f"Artifact saved successfully for project {project_id}")
        
        # Автоматический вызов C1.2 (Patch Architect) для декомпозиции L2
        try:
            result = await services.trigger_decomposition(l2_data)
            logger.info(f"Decomposition triggered successfully: {result}")
        except Exception as e:
            logger.error(f"Failed to trigger decomposition: {e}")
            # Не прерываем диалог, только логируем
        
        patches = await _call_c12(project_id, l2_data)
        print(f"DEBUG _process_l2_response: C1.2 called, patches count: {len(patches) if patches else 0}")
        
        # Вызов интегратора
        task_id = None
        if patches:
            logger.info(f"Calling integrator for project {project_id} with {len(patches)} patches")
            logger.info(f"DEBUG patches: {patches}")
            task_id = await create_task_in_registry(l2_data, project_id)
            logger.info(f"DEBUG: create_task_in_registry returned task_id = {task_id}")
            if task_id:
                try:
                    logger.info(f"DEBUG: About to call integrator with patches {patches} and task_id {task_id}")
                    await call_integrator(patches, task_id)
                    logger.info(f"Integrator called successfully for task {task_id}")
                    # Обновляем статус задачи в handover
                    repo.update_task_status(task_id, "ON_REVIEW", "Patches sent to integrator, build started")
                except Exception as e:
                    logger.error(f"Integrator call failed: {e}")
                    repo.update_task_status(task_id, "BLOCKED", f"Integrator error: {str(e)}")
                    raise
            else:
                logger.error("Failed to create task in registry, cannot call integrator")
                raise ValueError("Task creation failed")
        else:
            logger.warning(f"No patches returned from C1.2 for project {project_id}")
            task_id = await create_task_in_registry(l2_data, project_id)
            logger.info(f"DEBUG: create_task_in_registry (no patches) returned task_id = {task_id}")
            if task_id:
                repo.update_task_status(task_id, "REWORK", "No patches generated, check L2")
        
        # Возвращаем сообщение как указано в задании
        assistant_message = "✅ Проект сформирован, передан архитектору."
        completed = True
        task_description = l2_data
        collected.update(l2_data)
        logger.info(f"L2 processed successfully: saved artifact, called C1.2, created task {task_id}")
        return assistant_message, completed, task_id, task_description
    except Exception as e:
        print(f"DEBUG _process_l2_response: exception {e}")
        logger.error(f"Failed to process L2: {e}", exc_info=True)
        return "Не удалось запустить проектирование. Обратитесь к администратору.", False, None, None


async def _ensure_project_exists(project_id: str, message: str) -> Tuple[str, str, list, dict]:
    """Проверяет существование проекта в C2.6. НЕ СОЗДАЁТ НОВЫЕ ПРОЕКТЫ."""
    import httpx
    
    session_id = project_id
    try:
        history, collected = repo.get_session(session_id)
    except Exception as e:
        logger.error(f"Failed to get session from repo: {e}", exc_info=True)
        history, collected = [], {}
    
    logger.info(f"_ensure_project_exists: session_id={session_id}, history length={len(history)}, collected keys={list(collected.keys())}")
    
    # Если история есть, значит проект уже использовался в диалоге
    if history:
        logger.info("History exists, returning existing session")
        return project_id, session_id, history, collected
    
    # Проверяем существование проекта в C2.6
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{PROJECT_MEMORY_URL}/projects/{project_id}", timeout=5.0)
            if resp.status_code == 404:
                logger.error(f"Project {project_id} not found in C2.6")
                await send_log_to_br18("project_not_found", {"project_id": project_id})
                raise ValueError("Project not found")
            resp.raise_for_status()
            logger.info(f"Project {project_id} exists in C2.6")
            await send_log_to_br18("project_verified", {"project_id": project_id})
    except Exception as e:
        logger.error(f"Failed to check project {project_id}: {e}")
        await send_log_to_br18("project_check_error", {"project_id": project_id, "error": str(e)})
        raise
    
    return project_id, session_id, history, collected


async def background_processing(project_id: str, task_description: dict, task_id: str):
    """Фоновая обработка задачи: декомпозиция и интеграция."""
    await send_log_to_br18("decomposition_started", {"task_id": task_id})
    description_text = task_description.get("description", "") or json.dumps(task_description, ensure_ascii=False)
    patches = await call_decomposer(description_text, task_id)
    if patches:
        await send_log_to_br18("decomposition_completed", {"task_id": task_id, "patches_count": len(patches)})
        repo.update_task_status(task_id, "IN_PROGRESS", f"Decomposed into {len(patches)} patches")
        await call_integrator(patches, task_id)
    else:
        await send_log_to_br18("decomposition_completed", {"task_id": task_id, "patches_count": 0})
        logger.info(f"No patches returned for task {task_id}")
        repo.update_task_status(task_id, "NEW", "Decomposition returned no patches")