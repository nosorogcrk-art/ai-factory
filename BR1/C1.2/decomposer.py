#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
decomposer.py – разбиение крупных задач на атомарные патчи.
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/decomposer.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_registry() -> List[Dict[str, Any]]:
    if not TASK_REGISTRY_PATH.exists():
        return []
    with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: List[Dict[str, Any]]) -> None:
    with open(TASK_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def _generate_patches(description: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Генерирует список патчей на основе описания."""
    patches = []
    if "логирование" in description.lower():
        patches.append({
            "title": "Улучшить формат логов",
            "description": "Добавить временные метки и уровни логирования во все скрипты агентов."
        })
        patches.append({
            "title": "Добавить ротацию логов",
            "description": "Настроить автоматическое удаление старых логов."
        })
    elif "промпт" in description.lower():
        patches.append({
            "title": "Оптимизировать промпт Гефеста",
            "description": "Улучшить инструкции для агента Гефест, добавить примеры."
        })
    else:
        patches.append({
            "title": f"Реализовать: {description[:50]}...",
            "description": description
        })
    return patches


def decompose(description: str, context: Dict[str, Any]) -> List[str]:
    """
    Разбивает задачу на атомарные патчи и сохраняет их в реестр.

    Args:
        description: Описание задачи.
        context: Дополнительный контекст (например, task_id).

    Returns:
        Список ID созданных патчей.
    """
    registry = load_registry()
    patches = _generate_patches(description, context)

    created_ids = []
    for patch in patches:
        date_str = datetime.now().strftime("%Y%m%d")
        count = sum(1 for t in registry if t["id"].startswith(f"IMP-{date_str}"))
        new_id = f"IMP-{date_str}-{count+1:03d}"
        task = {
            "id": new_id,
            "title": patch["title"],
            "description": patch["description"],
            "status": "NEW",
            "assigned_to": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "history": [],
            "type": "improvement"
        }
        registry.append(task)
        created_ids.append(new_id)
        logger.info(f"Created patch {new_id}: {patch['title']}")

    save_registry(registry)
    return created_ids