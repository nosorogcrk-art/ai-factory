import logging
import json
from pathlib import Path
from typing import Optional, Tuple
import repositories as repo
from llm_client import _call_llm, _parse_l2_response
from external_api import _save_message, call_skill_integrator
from handlers import _process_l2_response, _ensure_project_exists, send_log_to_br18, background_processing as handlers_background_processing

HINTS_DIR = Path("01_ЦЕХ/ПОДСКАЗКИ")

def load_hints(project_id: str) -> dict:
    hints_file = HINTS_DIR / f"{project_id}_hints.json"
    if hints_file.exists():
        with open(hints_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

logger = logging.getLogger(__name__)


async def background_processing(project_id: str, task_description: dict, task_id: str):
    """Фоновая обработка задачи: декомпозиция и интеграция."""
    return await handlers_background_processing(project_id, task_description, task_id)


async def process_dialog(project_id: str, message: str) -> Tuple[str, bool, Optional[str], Optional[dict]]:
    """Основная функция обработки диалога."""
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
    # await send_log_to_br18("user_message", {"project_id": project_id, "message": message})
    # await _save_message(project_id, "user", message)

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
    else:
        logger.info(f"DEBUG: Using existing system prompt from collected for project {project_id}")

    messages = [{"role": "system", "content": system_prompt}] + history[-20:]

    assistant_message = await _call_llm(messages)
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