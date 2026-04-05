"""Бизнес-логика Project Dashboard."""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import httpx
import models

logger = logging.getLogger(__name__)


async def fetch_json(url: str, default: Optional[Dict] = None) -> Dict:
    """
    Асинхронно загружает JSON по URL.

    Args:
        url: Адрес для запроса.
        default: Значение по умолчанию при ошибке.

    Returns:
        Словарь с данными или default.
    """
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return default or {}


def read_tasks(task_registry_path: str) -> List[Dict]:
    """
    Читает реестр задач из файла.

    Args:
        task_registry_path: Путь к файлу task_registry.json.

    Returns:
        Список задач.
    """
    from pathlib import Path
    path = Path(task_registry_path)
    if not path.exists():
        logger.warning(f"Task registry not found: {task_registry_path}")
        return []
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        return tasks
    except Exception as e:
        logger.error(f"Error reading task registry: {e}")
        return []


async def aggregate_status(
    registry_url: str,
    metrics_url: str,
    skill_registry_url: str,
    task_registry_path: str
) -> models.MetricsResponse:
    """
    Агрегирует статус из нескольких источников.

    Args:
        registry_url: URL BR0 Registry.
        metrics_url: URL C18.2 Metrics Dashboard.
        skill_registry_url: URL C17.1 Skill Registry.
        task_registry_path: Путь к реестру задач.

    Returns:
        Объект MetricsResponse.
    """
    branches_data = await fetch_json(f"{registry_url}/branches", {"branches": []})
    metrics = await fetch_json(f"{metrics_url}/api/metrics", {})
    skill_stats = await fetch_json(f"{skill_registry_url}/skills/stats", {"total": 0, "active": 0})
    tasks = read_tasks(task_registry_path)

    return models.MetricsResponse(
        metrics=metrics,
        branches=branches_data.get("branches", []),
        tasks=tasks,
        skill_stats=skill_stats,
        last_update=datetime.now().isoformat()
    )