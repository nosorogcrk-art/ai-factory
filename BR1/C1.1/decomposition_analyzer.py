import json
import logging
import re
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
INTEGRATOR_LOG_PATH = Path("01_ЦЕХ/01_ЖУРНАЛЫ/integrator.log")
ANALYSIS_DIR = Path("01_ЦЕХ/МЕТРИКИ/decomposition_analysis")
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

SKILL_EXECUTE_URL = "http://skill-integrator:8090/execute"

def load_task_registry() -> List[Dict[str, Any]]:
    """Загружает реестр задач из JSON."""
    if not TASK_REGISTRY_PATH.exists():
        logger.warning(f"Task registry not found at {TASK_REGISTRY_PATH}")
        return []
    with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def parse_integrator_log(since_days: int = 7) -> Dict[str, Any]:
    """Парсит лог интегратора, извлекая успешные/неудачные сборки по task_id."""
    if not INTEGRATOR_LOG_PATH.exists():
        logger.warning(f"Integrator log not found at {INTEGRATOR_LOG_PATH}")
        return {"success": [], "failures": []}
    # cutoff = datetime.now() - timedelta(days=since_days)  # Пока не используется
    success = []
    failures = []
    with open(INTEGRATOR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            # Ищем строки вида: POST /build HTTP/1.1 200 OK (успех) или 500 (ошибка)
            if "POST /build" in line:
                parts = line.split()
                status = None
                for i, part in enumerate(parts):
                    if part in ("200", "500"):
                        status = int(part)
                        break
                # Извлекаем task_id (можно по паттерну, например, "task_id=DIALOG-xxx")
                task_match = re.search(r'task_id[=:][\s]*["\']?([A-Za-z0-9\-_]+)', line)
                if task_match:
                    task_id = task_match.group(1)
                    if status == 200:
                        success.append(task_id)
                    elif status == 500:
                        failures.append(task_id)
    return {"success": success, "failures": failures}

def get_integrator_stats() -> Dict[str, Any]:
    """Собирает статистику интегратора для передачи в навык."""
    log_data = parse_integrator_log()
    return {
        "success_count": len(log_data["success"]),
        "failure_count": len(log_data["failures"]),
        "top_error_types": []  # можно расширить, если есть классификация ошибок
    }

async def call_decomposition_optimizer_skill(tasks: list, integrator_stats: dict) -> Optional[Dict[str, Any]]:
    """Вызывает навык decomposition_optimizer через C7.4 /execute."""
    context = {
        "tasks": tasks,
        "integrator_stats": integrator_stats
    }
    payload = {
        "task_type": "decomposition_optimizer",
        "context": context
    }
    try:
        logger.info(f"Calling skill at {SKILL_EXECUTE_URL}")
        async with httpx.AsyncClient() as client:
            resp = await client.post(SKILL_EXECUTE_URL, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            logger.info(f"Skill response: {data}")
            result = data.get("result")
            if not result:
                logger.error("No result field in response")
                return None
            return result
    except Exception as e:
        logger.error(f"Failed to call decomposition_optimizer skill: {e}")
        return None

async def run_decomposition_analysis() -> Dict[str, Any]:
    """Основная функция: собирает данные, вызывает навык, сохраняет отчёт."""
    logger.info("Starting decomposition analysis (skill-based)")
    tasks = load_task_registry()
    integrator_stats = get_integrator_stats()
    result = await call_decomposition_optimizer_skill(tasks, integrator_stats)
    logger.info(f"Skill call result: {result}")
    if result is None:
        result = {"analysis": "Не удалось получить рекомендации", "rules": []}
    
    # Сохраняем отчёт
    report_file = ANALYSIS_DIR / f"analysis_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "analysis": result.get("analysis", ""),
            "rules": result.get("rules", []),
            "raw_result": result
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Decomposition analysis saved to {report_file}")
    
    # Сохраняем правила отдельно
    rules_file = ANALYSIS_DIR / "decomposition_rules.json"
    with open(rules_file, "w", encoding="utf-8") as f:
        json.dump({"generated_at": datetime.now().isoformat(), "rules": result.get("rules", [])}, f, indent=2)
    logger.info(f"Rules saved to {rules_file}")
    return result

async def decomposition_analyzer_scheduler(interval_seconds: int = 86400):
    """Фоновый планировщик, запускающий анализ раз в сутки."""
    while True:
        await run_decomposition_analysis()
        await asyncio.sleep(interval_seconds)
