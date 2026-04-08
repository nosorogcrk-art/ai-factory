import json
import asyncio
import logging
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

INTEGRATOR_LOG_PATH = Path("01_ЦЕХ/01_ЖУРНАЛЫ/integrator.log")
TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
AUDIT_DIR = Path("01_ЦЕХ/МЕТРИКИ/integrator_audit")
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

SKILL_EXECUTE_URL = "http://skill-integrator:8090/execute"

def get_integrator_stats_and_errors(since_days: int = 7) -> Dict[str, Any]:
    """Парсит лог интегратора, возвращает статистику и выборку ошибок."""
    cutoff = datetime.now() - timedelta(days=since_days)
    success = 0
    failure = 0
    error_types = []
    error_samples = []
    
    if not INTEGRATOR_LOG_PATH.exists():
        logger.warning(f"Integrator log not found at {INTEGRATOR_LOG_PATH}")
        return {
            "success_count": 0,
            "failure_count": 0,
            "top_error_types": [],
            "error_samples": []
        }
    
    with open(INTEGRATOR_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            # Извлекаем timestamp (пример: 2026-04-07 10:00:00)
            ts_match = None
            if len(line) > 19:
                ts_match = line[:19]
            if ts_match:
                try:
                    dt = datetime.strptime(ts_match, "%Y-%m-%d %H:%M:%S")
                    if dt < cutoff:
                        continue
                except ValueError:
                    pass
            if '"POST /build HTTP/1.1" 200' in line:
                success += 1
            elif '"POST /build HTTP/1.1" 500' in line:
                failure += 1
                error_types.append("500")
                # извлекаем task_id
                import re
                task_match = re.search(r'task_id[=:][\s]*["\']?([A-Za-z0-9\-_]+)', line)
                task_id = task_match.group(1) if task_match else "unknown"
                patch_match = re.search(r'patch_ids?[=:][\s]*["\']?([A-Za-z0-9\-_]+)', line)
                patch_id = patch_match.group(1) if patch_match else None
                error_samples.append({
                    "timestamp": ts_match,
                    "task_id": task_id,
                    "patch_id": patch_id,
                    "error_type": "500",
                    "message": line.strip()[:200]
                })
            elif "Conflict" in line or "conflict" in line.lower():
                failure += 1
                error_types.append("conflict")
                task_match = re.search(r'task_id[=:][\s]*["\']?([A-Za-z0-9\-_]+)', line)
                task_id = task_match.group(1) if task_match else "unknown"
                error_samples.append({
                    "timestamp": ts_match,
                    "task_id": task_id,
                    "patch_id": None,
                    "error_type": "conflict",
                    "message": line.strip()[:200]
                })
    # Топ-3 типов ошибок
    from collections import Counter
    top_error_types = [item for item, count in Counter(error_types).most_common(3)]
    return {
        "success_count": success,
        "failure_count": failure,
        "top_error_types": top_error_types,
        "error_samples": error_samples[-15:]  # последние 15
    }

def get_tasks_summary(limit: int = 20) -> List[Dict]:
    """Загружает реестр патчей и возвращает краткую информацию о задачах."""
    if not TASK_REGISTRY_PATH.exists():
        logger.warning(f"Task registry not found at {TASK_REGISTRY_PATH}")
        return []
    with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
        registry = json.load(f)
    # Берем последние `limit` задач
    tasks = registry[-limit:] if len(registry) > limit else registry
    summary = []
    for task in tasks:
        summary.append({
            "id": task.get("id"),
            "status": task.get("status"),
            "dependencies": task.get("dependencies", [])
        })
    return summary

async def call_integrator_audit_skill(period_days: int = 7) -> Optional[Dict]:
    """Собирает данные, вызывает /execute у C7.4, возвращает результат."""
    integrator_data = get_integrator_stats_and_errors(since_days=period_days)
    tasks_summary = get_tasks_summary(limit=20)
    context = {
        "period_days": period_days,
        "integrator_stats": {
            "success_count": integrator_data["success_count"],
            "failure_count": integrator_data["failure_count"],
            "top_error_types": integrator_data["top_error_types"]
        },
        "error_samples": integrator_data["error_samples"],
        "tasks_summary": tasks_summary
    }
    payload = {
        "task_type": "integrator_audit",
        "context": context
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(SKILL_EXECUTE_URL, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = await resp.json()
            result = data.get("result")
            if not result:
                logger.error("No result field in response")
                return None
            return result
    except Exception as e:
        logger.error(f"Failed to call integrator audit skill: {e}")
        return None

async def run_integrator_audit(period_days: int = 7) -> Dict[str, Any]:
    """Основная функция: вызывает навык, сохраняет отчёт."""
    logger.info("Starting integrator audit")
    result = await call_integrator_audit_skill(period_days)
    if result is None:
        result = {
            "analysis": "Не удалось получить рекомендации",
            "recommendations": [],
            "risk_level": "unknown"
        }
    report_file = AUDIT_DIR / f"audit_{datetime.now().strftime('%Y-%m-%d')}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "period_days": period_days,
            "analysis": result.get("analysis", ""),
            "recommendations": result.get("recommendations", []),
            "risk_level": result.get("risk_level", "unknown")
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Integrator audit report saved to {report_file}")
    return result

async def integrator_audit_scheduler(interval_seconds: int = 86400):
    """Фоновый планировщик, запускающий аудит раз в сутки."""
    while True:
        await run_integrator_audit()
        await asyncio.sleep(interval_seconds)