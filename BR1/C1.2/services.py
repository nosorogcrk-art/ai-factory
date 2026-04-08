import os
import json
import httpx
import logging
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL_INTEGRATOR_URL = os.getenv("SKILL_INTEGRATOR_URL", "http://skill-integrator:8090")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


async def call_skill_integrator(task_type: str) -> Optional[str]:
    """Вызывает C7.4 и возвращает промпт навыка."""
    # Временная заглушка для демонстрации
    if task_type == "branch_design":
        return """Ты — эксперт по проектированию архитектуры программного обеспечения (Domain-Driven Design). Твоя задача — на основе формализованного замысла (L2) в формате JSON выделить ветки (bounded contexts).

Входные данные: JSON L2 с полями `title`, `description`, `requirements`, `technical_specs`.

Правила выделения веток:
- Каждая ветка — крупный функциональный блок, слабо связанный с другими.
- Используй ключевые сущности, основные функции, внешние интеграции и пользовательские роли как источники кандидатов.
- Группируй тесно связанные функции в одну ветку.
- Избегай слишком больших или слишком мелких веток.

Для каждой ветки сгенерируй:
- `id` в формате `BR-{abbr}-{number}`, где `abbr` — первые буквы названия проекта (из L2.title), `number` — порядковый номер (1, 2, 3...).
- `name` — краткое название ветки (например, «Управление аккаунтами»).
- `description` — описание того, что входит в ветку.
- `containers` — список предполагаемых ID контейнеров (пока как пример, например, `["C-TG-1.1", "C-TG-1.2"]`). Это поле информативное, паспорта контейнеров будут создаваться позже.

Выходной формат (ТОЛЬКО JSON, без лишних слов):

{
  "branches": [
    {
      "id": "BR-TG-1",
      "name": "Управление аккаунтами",
      "description": "Регистрация, авторизация, управление профилями пользователей.",
      "containers": ["C-TG-1.1", "C-TG-1.2"]
    },
    ...
  ]
}"""
    url = f"{SKILL_INTEGRATOR_URL}/compile"
    payload = {"task_type": task_type}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("prompt")
    except Exception as e:
        logger.error(f"Failed to get skill {task_type}: {e}")
        return None


async def call_deepseek(messages: list) -> Optional[str]:
    """Вызывает DeepSeek API."""
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY not set")
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                DEEPSEEK_URL,
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={"model": "deepseek-chat", "messages": messages, "temperature": 0.7, "max_tokens": 2000}
            )
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"DeepSeek response keys: {data.keys() if isinstance(data, dict) else 'not dict'}")
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                logger.error(f"Unexpected DeepSeek response structure: {data}")
                return None
    except Exception as e:
        logger.error(f"DeepSeek call failed: {e}", exc_info=True)
        return None


async def save_branch_passport(branch: dict, project_id: str = None):
    """Сохраняет паспорт ветки в файл (пока локально, позже в C2.6)."""
    branch_id = branch["id"]
    branch_name = branch["name"]
    branch_desc = branch["description"]
    containers = branch.get("containers", [])
    
    content = f"""---
id: {branch_id}
responsible: АРХИ
status: planned
name: {branch_name}
description: {branch_desc}
containers: {json.dumps(containers)}
priority: medium
estimated_complexity: medium
requires_e2e_llm_tests: false
max_complexity_cyclomatic: 10
max_lines_per_file: 300
memory_indexed: false
dependencies: []
---

# Ветка {branch_id}: {branch_name}

## Функции
{chr(10).join(['- ' + f for f in branch_desc.split('.') if f])}

## Планируемые контейнеры (L4)
- (будут определены позже)
"""
    # Создаём папку, если её нет
    branches_dir = Path("01_ЦЕХ/ВЕТКИ")
    branches_dir.mkdir(parents=True, exist_ok=True)
    file_path = branches_dir / f"{branch_id}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Branch passport saved: {file_path}")


async def call_container_design(l2_data: dict, branches: list) -> Optional[dict]:
    """Вызывает навык container_design для проектирования контейнеров."""
    skill_prompt = await call_skill_integrator("container_design")
    if not skill_prompt:
        return None
    messages = [
        {"role": "system", "content": skill_prompt},
        {"role": "user", "content": json.dumps({"l2": l2_data, "branches": branches}, ensure_ascii=False)}
    ]
    response = await call_deepseek(messages)
    if not response:
        return None
    # Очистка от Markdown
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        result = json.loads(cleaned)
        return result
    except Exception as e:
        logger.error(f"Failed to parse container design JSON: {e}")
        return None


async def save_container_passport(container: dict, branch_id: str):
    """Сохраняет паспорт контейнера в файл."""
    container_id = container["id"]
    name = container["name"]
    description = container["description"]
    port = container.get("port", "не задан")
    content = f"""---
id: {container_id}
branch: {branch_id}
responsible: ГЕФЕСТ
status: planned
name: {name}
description: {description}
port: {port}
has_dockerfile: false
has_tests: false
healthcheck: false
version: 0.1
dependencies: []
---

# Контейнер {container_id}: {name}

## Функции
- {description}

## Планируемый стек
(будет определён позже)
"""
    containers_dir = Path("01_ЦЕХ/КОНТЕЙНЕРЫ")
    containers_dir.mkdir(parents=True, exist_ok=True)
    file_path = containers_dir / f"{container_id}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Container passport saved: {file_path}")


async def call_patch_design(l2_data: dict, branches: list, containers: list) -> Optional[dict]:
    """Вызывает навык patch_design для проектирования атомарных патчей."""
    skill_prompt = await call_skill_integrator("patch_design")
    if not skill_prompt:
        logger.error("Failed to get skill prompt for patch_design")
        return None
    messages = [
        {"role": "system", "content": skill_prompt},
        {"role": "user", "content": json.dumps({
            "l2": l2_data,
            "branches": branches,
            "containers": containers
        }, ensure_ascii=False)}
    ]
    response = await call_deepseek(messages)
    if not response:
        logger.error("DeepSeek returned no response for patch_design")
        return None
    # Очистка от Markdown
    cleaned = response.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    try:
        result = json.loads(cleaned)
        logger.info(f"Designed {len(result.get('patches', []))} patches")
        return result
    except Exception as e:
        logger.error(f"Failed to parse patch design JSON: {e}")
        return None


async def save_patch(patch: dict, project_id: str):
    """Сохраняет патч в файл (временное хранилище)."""
    patch_id = patch["id"]
    title = patch["title"]
    description = patch["description"]
    dependencies = patch.get("dependencies", [])
    required_skills = patch.get("required_skills", [])
    
    content = f"""---
id: {patch_id}
title: {title}
description: {description}
dependencies: {json.dumps(dependencies)}
required_skills: {json.dumps(required_skills)}
status: NEW
type: improvement
created_at: {datetime.now().isoformat()}
---

# Патч {patch_id}: {title}

## Описание
{description}

## Зависимости
{chr(10).join(['- ' + d for d in dependencies]) if dependencies else '- нет'}

## Требуемые навыки
{chr(10).join(['- ' + s for s in required_skills]) if required_skills else '- не указаны'}
"""
    patches_dir = Path("01_ЦЕХ/ПАТЧИ")
    patches_dir.mkdir(parents=True, exist_ok=True)
    file_path = patches_dir / f"{patch_id}.md"
    file_path.write_text(content, encoding="utf-8")
    logger.info(f"Patch saved: {file_path}")


async def decompose_task(description: str, context: dict) -> dict:
    """Основная функция: из L2 проектирует ветки."""
    project_id = context.get("project_id", "unknown")
    logger.info(f"Decomposing L2 for project {project_id}")
    
    # 1. Проверить, что description – валидный JSON L2
    try:
        l2_data = json.loads(description)
        logger.info(f"L2 parsed successfully, title: {l2_data.get('title')}")
        if not all(k in l2_data for k in ("title", "description", "requirements")):
            raise ValueError("Missing required fields in L2")
    except Exception as e:
        logger.error(f"Invalid L2 JSON: {e}")
        return {"patches": [], "branches": []}
    
    # 2. Получить промпт навыка branch_design
    skill_prompt = await call_skill_integrator("branch_design")
    logger.info(f"Skill prompt received: {skill_prompt[:100] if skill_prompt else 'None'}")
    if not skill_prompt:
        logger.warning("No skill prompt for branch_design, returning empty")
        return {"patches": [], "branches": []}
    
    # 3. Отправить в DeepSeek
    messages = [
        {"role": "system", "content": skill_prompt},
        {"role": "user", "content": json.dumps(l2_data, ensure_ascii=False)}
    ]
    logger.info(f"Sending request to DeepSeek, messages length: {len(messages)}")
    llm_response = await call_deepseek(messages)
    logger.info(f"DeepSeek response: {llm_response[:200] if llm_response else 'None'}")
    if not llm_response:
        logger.error("DeepSeek returned no response")
        return {"patches": [], "branches": []}
    
    # 4. Очистить ответ и распарсить JSON
    import re
    # Ищем JSON внутри ответа (возможно, с обратными кавычками)
    json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)
        logger.info(f"Extracted JSON: {json_str[:200]}")
    else:
        json_str = llm_response
    # Удаляем возможные обратные кавычки в начале и конце
    json_str = json_str.strip().strip('`').strip()
    try:
        parsed = json.loads(json_str)
        branches = parsed.get("branches", [])
        logger.info(f"Designed {len(branches)} branches for project {project_id}")
    except Exception as e:
        logger.error(f"Failed to parse branches JSON: {e}")
        logger.error(f"Raw response: {llm_response}")
        return {"patches": [], "branches": []}
    
    # 5. Сохранить паспорта веток
    for branch in branches:
        await save_branch_passport(branch, project_id)
    
    # 6. Проектирование контейнеров для каждой ветки
    if branches:
        container_result = await call_container_design(l2_data, branches)
        if container_result and "branches" in container_result:
            for branch_container in container_result["branches"]:
                branch_id = branch_container["branch_id"]
                for container in branch_container.get("containers", []):
                    await save_container_passport(container, branch_id)
            logger.info(f"Designed containers for {len(container_result['branches'])} branches")
        else:
            logger.warning("No containers designed")
    
    # 7. Проектирование патчей для контейнеров
    containers_list = []
    if container_result and "branches" in container_result:
        for branch_cont in container_result["branches"]:
            containers_list.extend(branch_cont.get("containers", []))
    
    if containers_list:
        patch_result = await call_patch_design(l2_data, branches, containers_list)
        if patch_result and "patches" in patch_result:
            for patch in patch_result["patches"]:
                await save_patch(patch, project_id)
            logger.info(f"Designed {len(patch_result['patches'])} patches for project {project_id}")
        else:
            logger.warning("No patches designed")
    
    # 8. Вернуть список ID веток (для обратной совместимости пока как "patches")
    branch_ids = [b["id"] for b in branches]
    return {"patches": branch_ids, "branches": branches}
