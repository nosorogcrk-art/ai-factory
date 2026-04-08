import json
import os
import asyncio
import logging
import httpx
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)

# Директории с отчётами
REPORT_DIRS = {
    "prompt_analysis": Path("01_ЦЕХ/МЕТРИКИ/prompt_analysis"),
    "decomposition_analysis": Path("01_ЦЕХ/МЕТРИКИ/decomposition_analysis"),
    "integrator_audit": Path("01_ЦЕХ/МЕТРИКИ/integrator_audit")
}

# Маппинг типа отчёта на роль в handover
REPORT_TO_ROLE = {
    "prompt_analysis": "ARCHITECT",
    "decomposition_analysis": "ARCHITECT",
    "integrator_audit": "HEPHESTUS"
}

# URL для создания задач в handover (можно переопределить через переменную окружения)
HANDOVER_TASKS_URL = os.getenv("HANDOVER_URL", "http://handover:8080/tasks")

def scan_reports() -> List[tuple]:
    """
    Возвращает список (report_path, report_type, report_data) для всех непроцессированных отчётов.
    """
    reports = []
    for report_type, dir_path in REPORT_DIRS.items():
        if not dir_path.exists():
            logger.warning(f"Report directory does not exist: {dir_path}")
            continue
        for file_path in dir_path.glob("analysis_*.json"):
            processed_flag = file_path.with_suffix(file_path.suffix + ".processed")
            if processed_flag.exists():
                continue  # уже обработан
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                reports.append((file_path, report_type, data))
            except Exception as e:
                logger.error(f"Failed to read report {file_path}: {e}")
    return reports

def should_create_task(report_data: Dict) -> bool:
    """
    Определяет, нужно ли создавать задачу на основе отчёта.
    Критерий: risk_level == "high" ИЛИ есть непустые suggestions/recommendations.
    """
    risk_level = report_data.get("risk_level")
    if risk_level == "high":
        return True
    suggestions = report_data.get("suggestions") or report_data.get("recommendations") or []
    return len(suggestions) > 0

def build_task_payload(report_data: Dict, report_type: str, report_path: Path) -> Dict:
    """
    Формирует payload для POST /tasks.
    """
    suggestions = report_data.get("suggestions") or report_data.get("recommendations") or []
    analysis = report_data.get("analysis", "")
    title = f"Auto: {report_type.replace('_', ' ').title()} – {analysis[:80]}"
    description = f"Источник: {report_path}\n\nАнализ: {analysis}\n\nРекомендации:\n" + "\n".join(f"- {s}" for s in suggestions)
    assigned_role = REPORT_TO_ROLE.get(report_type, "ARCHITECT")
    priority = "high" if report_data.get("risk_level") == "high" else "medium"
    metadata = {
        "source": "daedalus_auto",
        "report_type": report_type,
        "report_path": str(report_path),
        "risk_level": report_data.get("risk_level", "unknown")
    }
    return {
        "title": title,
        "description": description,
        "assigned_role": assigned_role,
        "priority": priority,
        "metadata": metadata
    }

async def create_task_in_handover(payload: Dict) -> bool:
    """
    Отправляет POST запрос в C7.2 для создания задачи.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(HANDOVER_TASKS_URL, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info(f"Task created in handover: {payload['title'][:50]}")
            return True
    except Exception as e:
        logger.error(f"Failed to create task in handover: {e}")
        return False

def mark_report_processed(report_path: Path):
    """
    Создаёт файл-флаг .processed рядом с отчётом.
    """
    flag = report_path.with_suffix(report_path.suffix + ".processed")
    flag.touch()
    logger.info(f"Report marked as processed: {flag}")

async def run_auto_patch_initiation():
    """
    Основная функция: сканирует отчёты, создаёт задачи для тех, где нужно, помечает обработанными.
    """
    logger.info("Starting auto patch initiation scan")
    reports = scan_reports()
    if not reports:
        logger.info("No new reports found")
        return
    created = 0
    for report_path, report_type, report_data in reports:
        if should_create_task(report_data):
            payload = build_task_payload(report_data, report_type, report_path)
            success = await create_task_in_handover(payload)
            if success:
                mark_report_processed(report_path)
                created += 1
        else:
            # Если задача не требуется, всё равно пометим как обработанный, чтобы не сканировать повторно
            mark_report_processed(report_path)
            logger.info(f"Skipped (no high risk or suggestions): {report_path}")
    logger.info(f"Auto patch initiation finished, created {created} tasks")

async def auto_patch_scheduler(interval_seconds: int = 3600):
    """
    Фоновый планировщик, запускающий сканирование раз в час.
    """
    while True:
        await run_auto_patch_initiation()
        await asyncio.sleep(interval_seconds)