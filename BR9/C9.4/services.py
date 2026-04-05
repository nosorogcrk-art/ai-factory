import os
import json
import uuid
import logging
import httpx
from datetime import datetime, timezone
from typing import Optional, Tuple
import repositories as repo

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
HANDOVER_URL = os.getenv("HANDOVER_URL", "http://handover:8080")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
PROJECT_MEMORY_URL = os.getenv("PROJECT_MEMORY_URL", "http://project-memory:8090")
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)

DECOMPOSER_URL = os.getenv("DECOMPOSER_URL", "http://patch-architect:8085")
INTEGRATOR_URL = os.getenv("INTEGRATOR_URL", "http://integrator:8096")

async def send_log_to_br18(event_type: str, details: dict):
    log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "C9.4", "event_type": event_type, "details": details}
    try:
        await client.post(BR18_URL, json=log_entry)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

async def save_message_to_project(project_id: str, role: str, content: str, message_type: str = "text"):
    try:
        resp = await client.post(f"{PROJECT_MEMORY_URL}/projects/{project_id}/messages",
                                 json={"role": role, "content": content, "message_type": message_type}, timeout=5.0)
        resp.raise_for_status()
        logger.info(f"Message saved to project {project_id}")
    except Exception as e:
        logger.error(f"Failed to save message to project {project_id}: {e}")

async def create_task_in_registry(description: dict, project_id: str) -> Optional[str]:
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

async def call_decomposer(description: str, task_id: str) -> list:
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
    url = f"{INTEGRATOR_URL}/build"
    payload = {"task_id": task_id, "patch_ids": patch_ids, "check_skills": True, "run_tests": True}
    try:
        resp = await client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        logger.info(f"Integrator triggered with {len(patch_ids)} patches for task {task_id}")
        await send_log_to_br18("integration_triggered", {"task_id": task_id, "patch_ids": patch_ids})
    except Exception as e:
        logger.error(f"Integrator call failed: {e}")
        await send_log_to_br18("integration_failed", {"task_id": task_id, "patch_ids": patch_ids, "error": str(e)})

async def background_processing(project_id: str, task_description: dict, task_id: str):
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

async def process_dialog(project_id: str, message: str) -> Tuple[str, bool, Optional[str], Optional[dict]]:
    session_id = project_id
    history, collected = repo.get_session(session_id)

    history.append({"role": "user", "content": message})
    await send_log_to_br18("user_message", {"project_id": project_id, "message": message})
    await save_message_to_project(project_id, "user", message, "text")

    system_prompt = (
        "Ты — ассистент, помогающий пользователю сформулировать задачу для разработки программного обеспечения. "
        "Задавай уточняющие вопросы, чтобы выяснить: что именно нужно сделать, на каком языке/платформе, какие требования, "
        "какой должен быть результат (архив, код, установщик). "
        "Когда соберёшь достаточно информации, верни JSON с полями: "
        "title, description, requirements (список), technical_specs (объект), deliverable (archive|code|setup), priority (high|medium|low), tags (список). "
        "Если нужно ещё уточнить, просто задай вопрос. "
        "Не включай в ответ ничего, кроме вопроса или JSON."
    )
    messages = [{"role": "system", "content": system_prompt}] + history[-20:]

    try:
        resp = await client.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.7, "max_tokens": 1000}
        )
        resp.raise_for_status()
        data = resp.json()
        assistant_message = data["choices"][0]["message"]["content"]
        await send_log_to_br18("llm_response", {"project_id": project_id, "response": assistant_message[:200]})
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        await send_log_to_br18("llm_error", {"error": str(e)})
        raise Exception("LLM service unavailable")

    completed = False
    task_id = None
    task_description = None
    try:
        parsed = json.loads(assistant_message)
        required_fields = ["title", "description", "requirements", "technical_specs", "deliverable", "priority", "tags"]
        missing = [f for f in required_fields if f not in parsed]
        if missing:
            assistant_message = f"Почти готово. Пожалуйста, уточните: {', '.join(missing)}."
            logger.info(f"JSON missing fields: {missing}")
        else:
            completed = True
            task_id = await create_task_in_registry(parsed, project_id)
            task_description = parsed
            assistant_message = f"✅ Задача сформирована! ID: {task_id}. В ближайшее время она будет обработана."
            collected.update(parsed)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON decode error: {e} | response: {assistant_message[:200]}")
        pass

    history.append({"role": "assistant", "content": assistant_message})
    repo.save_session(session_id, project_id, history, collected if completed else None)
    await save_message_to_project(project_id, "assistant", assistant_message, "text")

    if completed:
        await send_log_to_br18("dialogue_completed", {"project_id": project_id, "task_id": task_id})

    return assistant_message, completed, task_id, task_description