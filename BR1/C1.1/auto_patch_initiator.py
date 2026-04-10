import json
import os
import asyncio
import logging
import httpx
import glob
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

def calculate_risk_score(project_id: str) -> Dict[str, Any]:
    risk_score = 0
    reasons = []

    # 1. Анализ диалогов
    prompt_reports = glob.glob(f"01_ЦЕХ/МЕТРИКИ/prompt_analysis/*{project_id}*.json")
    for report in prompt_reports:
        try:
            with open(report, "r") as f:
                data = json.load(f)
                if data.get("suggestions") and len(data["suggestions"]) > 0:
                    risk_score += 1
                    reasons.append("Есть рекомендации по улучшению промпта")
                    break
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 2. Анализ декомпозиции
    decomp_reports = glob.glob("01_ЦЕХ/МЕТРИКИ/decomposition_analysis/*.json")
    for report in decomp_reports:
        try:
            with open(report, "r") as f:
                data = json.load(f)
                rules = data.get("generated_rules", [])
                if rules and "удовлетворительно" not in str(rules).lower():
                    risk_score += 1
                    reasons.append("Декомпозиция требует доработки")
                    break
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    # 3. Аудит интегратора
    audit_reports = glob.glob("01_ЦЕХ/МЕТРИКИ/integrator_audit/*.json")
    for report in audit_reports:
        try:
            with open(report, "r") as f:
                data = json.load(f)
                if data.get("recommendations") and len(data["recommendations"]) > 0:
                    risk_score += 1
                    reasons.append("Интегратор выдал рекомендации")
                    break
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    if risk_score >= 3:
        risk_level = "high"
    elif risk_score >= 2:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "reasons": reasons
    }


async def fetch_projects() -> List[Dict]:
    """Получает список проектов из C2.6 (project-memory) или через файловую систему."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get("http://project-memory:8090/projects")
            if resp.status_code == 200:
                return resp.json()
    except Exception:
        pass

    # Fallback: сканировать папку 01_ЦЕХ/ПРОЕКТЫ/
    projects = []
    projects_dir = "01_ЦЕХ/ПРОЕКТЫ/"
    if os.path.exists(projects_dir):
        for item in os.listdir(projects_dir):
            if os.path.isdir(os.path.join(projects_dir, item)):
                projects.append({"id": item})
    return projects


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


async def create_handover_task(
    title: str,
    description: str,
    assigned_role: str,
    priority: str = "medium"
) -> bool:
    """
    Создаёт задачу в handover системе (обёртка для совместимости).
    """
    payload = {
        "title": title,
        "description": description,
        "assigned_role": assigned_role,
        "priority": priority,
        "metadata": {
            "source": "daedalus_risk_analysis",
            "timestamp": datetime.now().isoformat()
        }
    }
    return await create_task_in_handover(payload)


async def scan_projects_for_risk():
    projects = await fetch_projects()
    for project in projects:
        project_id = project["id"]
        risk = calculate_risk_score(project_id)
        if risk["risk_level"] == "high":
            # create_handover_task – асинхронная функция из существующего модуля
            await create_handover_task(
                title=f"Risk alert: project {project_id}",
                description=f"Risk level: {risk['risk_level']}\nReasons: {', '.join(risk['reasons'])}",
                assigned_role="ARGUS",
                priority="high"
            )
        # Сохранить отчёт (опционально, без ротации для упрощения)
        os.makedirs("01_ЦЕХ/МЕТРИКИ/risk_analysis/", exist_ok=True)
        report_path = f"01_ЦЕХ/МЕТРИКИ/risk_analysis/{project_id}_{datetime.now().isoformat()}.json"
        with open(report_path, "w") as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "project_id": project_id,
                **risk
            }, f, indent=2)

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