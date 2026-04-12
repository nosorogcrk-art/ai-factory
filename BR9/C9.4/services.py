import logging
import json
import httpx
import time
import os
from pathlib import Path
from typing import Optional, Tuple
import repositories as repo
from llm_client import _call_llm, _parse_l2_response
from external_api import _save_message, call_skill_integrator, send_log_to_br18, PROJECT_MEMORY_URL

HINTS_DIR = Path("01_ЦЕХ/ПОДСКАЗКИ")
PATCH_ARCHITECT_URL = "http://patch-architect:8085"  # порт C1.2


async def get_prompt_version(prompt_name: str) -> Optional[str]:
    """Получает версию промпта от C1.1 для A/B тестирования."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"http://cognitive-engine:8103/api/ab/version/prompt/{prompt_name}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version")
    except Exception as e:
        logger.warning(f"[AB] Failed to get version for prompt {prompt_name}: {e}")
    return None


async def send_ab_metric(experiment_id: str, variant: str, success: bool, duration_ms: int, cost_usd: float = 0.0, context: str = ""):
    """Отправляет метрику в C1.1 для A/B тестирования."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post("http://cognitive-engine:8103/api/ab/metrics", json={
                "experiment_id": experiment_id,
                "variant": variant,
                "success": success,
                "duration_ms": duration_ms,
                "cost_usd": cost_usd,
                "context": context
            })
    except Exception as e:
        logger.warning(f"[AB] Failed to send metric: {e}")


def load_hints(project_id: str) -> dict:
    hints_file = HINTS_DIR / f"{project_id}_hints.json"
    if hints_file.exists():
        with open(hints_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


async def trigger_decomposition(l2_data: dict) -> dict:
    """
    Вызывает C1.2 (Patch Architect) для декомпозиции L2.
    Возвращает результат вызова.
    """
    url = f"{PATCH_ARCHITECT_URL}/decompose"
    # C1.2 ожидает поле "description" (строка). Передаём весь L2 как JSON-строку.
    payload = {"description": json.dumps(l2_data, ensure_ascii=False)}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


logger = logging.getLogger(__name__)


async def background_processing(project_id: str, task_description: dict, task_id: str):
    """Фоновая обработка задачи: декомпозиция и интеграция."""
    from handlers import background_processing as handlers_background_processing
    return await handlers_background_processing(project_id, task_description, task_id)


async def process_dialog(project_id: str, message: str) -> Tuple[str, bool, Optional[str], Optional[dict]]:
    """Основная функция обработки диалога."""
    from handlers import _ensure_project_exists, _process_l2_response
    # Шаг 1: Проверяем, что project_id передан
    if not project_id:
        logger.error("project_id is required")
        return "Проект не найден. Сначала создайте проект через интерфейс.", False, None, None
    
    try:
        project_id, session_id, history, collected = await _ensure_project_exists(project_id, message)
    except ValueError as e:
        if str(e) == "Project not found":
            logger.error(f"Project {project_id} not found in C2.6")
            return "Проект не найден. Сначала создайте проект через интерфейс.", False, None, None
        else:
            logger.error(f"Error checking project existence: {e}")
            return "Не удалось проверить проект в памяти завода. Пожалуйста, попробуйте позже.", False, None, None
    except Exception as e:
        logger.error(f"Unexpected error in _ensure_project_exists: {e}", exc_info=True)
        return "Не удалось проверить проект в памяти завода. Пожалуйста, попробуйте позже.", False, None, None

    history.append({"role": "user", "content": message})
    await send_log_to_br18("user_message", {"project_id": project_id, "message": message})
    await _save_message(project_id, "user", message)

    # ПРОВЕРКА: принудительное создание L2 после 4 сообщений пользователя
    user_messages_count = await get_user_messages_count(project_id)
    print(f"DEBUG: User messages count for project {project_id}: {user_messages_count}")
    logger.info(f"User messages count for project {project_id}: {user_messages_count}")
    
    if user_messages_count >= 4:
        print(f"DEBUG: Project {project_id} has {user_messages_count} user messages, forcing L2 creation")
        logger.info(f"Project {project_id} has {user_messages_count} user messages, forcing L2 creation")
        # Получаем полную историю диалога из C2.6
        try:
            full_history = await get_dialog_history(project_id)
            # Формируем L2 на основе истории с помощью нового навыка l2_extractor
            l2_data = await call_l2_extractor(full_history)
            print(f"DEBUG: l2_extractor returned: {l2_data}")
            logger.info(f"Generated L2 for project {project_id}: {list(l2_data.keys())}")
            
            # Сохраняем L2 как артефакт
            print(f"DEBUG: Saving L2 artifact for project {project_id}")
            await save_l2_artifact(project_id, l2_data)
            logger.info(f"L2 artifact saved for project {project_id}")
            
            # Обрабатываем L2 через стандартный процесс
            assistant_message, completed, task_id, task_description = await _process_l2_response(
                project_id, l2_data, collected
            )
            
            # Сохраняем ответ ассистента
            history.append({"role": "assistant", "content": assistant_message})
            repo.save_session(session_id, project_id, history, collected)
            await _save_message(project_id, "assistant", assistant_message)
            
            if completed:
                await send_log_to_br18("dialogue_completed", {"project_id": project_id, "task_id": task_id})
            
            assistant_message = f"<!-- RAW: {assistant_message} -->\n{assistant_message}"
            return assistant_message, completed, task_id, task_description
            
        except Exception as e:
            print(f"DEBUG: Failed to force L2 creation for project {project_id}: {e}")
            import traceback
            print(traceback.format_exc())
            logger.error(f"Failed to force L2 creation for project {project_id}: {e}", exc_info=True)
            # Продолжаем обычный диалог в случае ошибки

    # Загрузка подсказок для нового диалога
    if not history:  # новый диалог
        hints_data = load_hints(project_id)
        if hints_data and hints_data.get("hints"):
            collected["hints"] = hints_data["hints"]
            logger.info(f"Loaded {len(hints_data['hints'])} hints for project {project_id}")
            # Добавляем подсказки в начало истории как системное сообщение
            hints_text = "\n".join([
                f"Пример успешного проекта {h['project_id']}: L2: {h.get('l2', {}).get('content', '')[:200]}"
                for h in hints_data["hints"] if h.get("l2")
            ])
            if hints_text:
                history.insert(0, {"role": "system", "content": f"Подсказки из похожих проектов:\n{hints_text}"})

    # Определяем системный промпт: загружаем из C7.4, если нет в collected
    system_prompt = collected.get("system_prompt")
    logger.info(f"DEBUG: Checking system prompt for project {project_id}. collected keys: {list(collected.keys())}, system_prompt present: {'system_prompt' in collected}")
    if not system_prompt:
        logger.info(f"No system prompt in collected for project {project_id}, calling C7.4 for discovery skill")
        
        # Получить версию промпта от C1.1 для A/B тестирования
        start_time = time.time()
        experiment_id = None
        variant = None
        version = await get_prompt_version("discovery")
        if version:
            logger.info(f"[AB] Using version {version} for prompt discovery")
            variant = version
            experiment_id = f"prompt_discovery"
        
        skill_response = await call_skill_integrator("discovery")
        logger.info(f"DEBUG: call_skill_integrator returned: {skill_response is not None}")
        
        if skill_response and "prompt" in skill_response:
            system_prompt = skill_response["prompt"]
            skill_id = skill_response.get("skill_id", "unknown")
            logger.info(f"Loaded skill {skill_id} for project {project_id}")
            await send_log_to_br18("skill_used", {"project_id": project_id, "skill_id": skill_id})
            
            # Сохраняем промпт в collected для использования в будущих сообщениях
            collected["system_prompt"] = system_prompt
            collected["skill_id"] = skill_id
            
            # Отправка метрики успеха
            if experiment_id and variant:
                duration_ms = int((time.time() - start_time) * 1000)
                await send_ab_metric(
                    experiment_id=experiment_id,
                    variant=variant,
                    success=True,
                    duration_ms=duration_ms,
                    context=f"prompt_discovery_success"
                )
        else:
            logger.warning(f"Failed to load skill from C7.4 for project {project_id}, using fallback prompt")
            await send_log_to_br18("skill_fallback", {"project_id": project_id})
            
            # Fallback: жёстко зашитый промпт
            system_prompt = (
                "Ты — главный ассистент системы «Цифровая Фабрика». Твоя задача — превратить сырую идею пользователя в формализованный замысел (L2).\n\n"
                "Твои обязанности (строго по порядку):\n\n"
                "1. Начни опрос по протоколу L1→L2 (5 блоков):\n"
                "   - **Блок 1 (Бизнес-цель):** Спроси: «Какую главную проблему вы хотите решить?»\n"
                "   - **Блок 2 (Аудитория):** Спроси: «Кто будет основными пользователями?»\n"
                "   - **Блок 3 (Функции):** Спроси: «Какие 3–5 самых важных действий должно выполнять приложение?»\n"
                "   - **Блок 4 (Технологии):** Спроси: «Есть ли технические ограничения или предпочтения?»\n"
                "   - **Блок 5 (Успех и бюджет):** Спроси: «Как мы поймём, что проект успешен? Есть ли бюджет?»\n\n"
                "   Если пользователь ответил не на всех уточняющих вопросы блока — задай один уточняющий вопрос (например: «Уточните, кто принимает решения?»). Не более одного уточнения на блок.\n\n"
                "2. После того как все 5 блоков собраны, сгенерируй L2 (Паспорт системы) в формате JSON:\n"
                "   - Используй структуру: `{\"title\": \"...\", \"description\": \"...\", \"requirements\": [...], \"technical_specs\": {...}}`.\n\n"
                "**Важно:** Ты не должен ничего придумывать сам. Только задавай вопросы из списка и генерируй L2 на основе ответов пользователя."
            )
            collected["system_prompt"] = system_prompt
            collected["skill_id"] = "fallback"
            
            # Отправка метрики ошибки
            if experiment_id and variant:
                duration_ms = int((time.time() - start_time) * 1000)
                await send_ab_metric(
                    experiment_id=experiment_id,
                    variant=variant,
                    success=False,
                    duration_ms=duration_ms,
                    context=f"prompt_discovery_fallback"
                )
    else:
        logger.info(f"DEBUG: Using existing system prompt from collected for project {project_id}")

    messages = [{"role": "system", "content": system_prompt}] + history[-20:]

    assistant_message = await _call_llm(messages)
    # Логирование входящего ответа для отладки
    logger.debug(f"Discovery response: {assistant_message[:500]}")
    is_l2, l2_data = _parse_l2_response(assistant_message)
    print(f"DEBUG services: is_l2={is_l2}, l2_data keys={list(l2_data.keys()) if isinstance(l2_data, dict) else 'not dict'}")
    logger.info(f"DEBUG: is_l2={is_l2}, l2_data keys={list(l2_data.keys()) if isinstance(l2_data, dict) else 'not dict'}")

    if is_l2:
        print(f"DEBUG services: calling _process_l2_response for project {project_id}")
        assistant_message, completed, task_id, task_description = await _process_l2_response(
            project_id, l2_data, collected
        )
    else:
        completed = False
        task_id = None
        task_description = None

    history.append({"role": "assistant", "content": assistant_message})
    logger.info(f"Saving session for session_id={session_id}, history length={len(history)}, collected keys={list(collected.keys())}")
    repo.save_session(session_id, project_id, history, collected)
    logger.info("Session saved")
    await _save_message(project_id, "assistant", assistant_message)

    if completed:
        await send_log_to_br18("dialogue_completed", {"project_id": project_id, "task_id": task_id})

    # ВРЕМЕННО: показать raw response в интерфейсе
    assistant_message = f"<!-- RAW: {assistant_message} -->\n{assistant_message}"
    return assistant_message, completed, task_id, task_description


async def get_user_messages_count(project_id: str) -> int:
    """Возвращает количество сообщений пользователя (role=user) в диалоге."""
    try:
        url = f"{PROJECT_MEMORY_URL}/projects/{project_id}/messages"
        logger.info(f"Getting user messages count from {url}")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            messages = resp.json()
            count = sum(1 for m in messages if m.get("role") == "user")
            logger.info(f"Found {count} user messages out of {len(messages)} total messages for project {project_id}")
            return count
    except Exception as e:
        logger.error(f"Failed to get user messages count for project {project_id}: {e}")
        return 0

async def get_dialog_history(project_id: str) -> list:
    """Получает историю сообщений проекта из C2.6."""
    url = f"{PROJECT_MEMORY_URL}/projects/{project_id}/messages"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.json()

async def save_l2_artifact(project_id: str, l2_data: dict) -> dict:
    """Сохраняет L2 (specification) как артефакт в C2.6, проверяя дубли."""
    url_check = f"{PROJECT_MEMORY_URL}/projects/{project_id}/artifacts"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url_check)
        resp.raise_for_status()
        artifacts = resp.json()
        existing = any(a.get("artifact_type") == "specification" for a in artifacts)
        if existing:
            logger.info(f"L2 already exists for project {project_id}, skipping")
            return {"status": "skipped", "message": "L2 already exists"}
        
        url = f"{PROJECT_MEMORY_URL}/projects/{project_id}/artifacts"
        payload = {
            "name": f"L2 specification for {project_id}",
            "artifact_type": "specification",
            "content": json.dumps(l2_data, ensure_ascii=False),
            "description": "L2 specification generated after dialog"
        }
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()

async def generate_l2_via_llm(messages: list) -> dict:
    """Прямой вызов DeepSeek для формирования L2 из истории диалога."""
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")
    prompt = f"""
На основе истории диалога пользователя и ассистента сформируй L2 – JSON с полями:
- "title": название проекта
- "description": описание проблемы/цели
- "requirements": массив строк с требованиями (минимум 2)
- "technical_specs": объект с техническими деталями (например, {{"stack": "Python", "api": "..."}})

История диалога:
{json.dumps(messages, indent=2, ensure_ascii=False)}

Верни ТОЛЬКО JSON без пояснений.
"""
    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data["choices"][0]["message"]["content"])

async def call_l2_extractor(messages: list) -> dict:
    """
    Вызывает навык l2_extractor для преобразования истории диалога в L2 JSON.
    Возвращает словарь с L2 данными.
    """
    skill_url = "http://skill-integrator:8090/execute"
    payload = {
        "task_type": "l2_extractor",
        "context": {
            "history": messages
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(skill_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            # Навык должен вернуть чистый JSON в поле "result" или сам результат
            if isinstance(result, dict) and "title" in result:
                return result
            elif isinstance(result, str):
                # Если результат - строка, пытаемся распарсить как JSON
                import json
                return json.loads(result)
            else:
                raise ValueError(f"Unexpected result format from l2_extractor: {result}")
    except Exception as e:
        logger.warning(f"Skill l2_extractor failed: {e}, falling back to direct LLM")
        # Fallback
        return await generate_l2_via_llm(messages)


async def finalize_l2(project_id: str, messages: list) -> dict:
    """
    Отправляет историю диалога в навык discovery с командой "finish".
    Если навык не возвращает l2, использует прямой вызов LLM.
    """
    skill_url = "http://skill-integrator:8090/execute"
    payload = {
        "task_type": "discovery",
        "context": {
            "action": "finish",
            "messages": messages
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(skill_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result", {})
            l2_data = result.get("l2")
            if l2_data:
                return l2_data
    except Exception as e:
        logger.warning(f"Skill discovery finish failed: {e}, falling back to direct LLM")
    # Fallback
    return await generate_l2_via_llm(messages)
