import json
import logging
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")


def load_registry() -> List[Dict[str, Any]]:
    if not TASK_REGISTRY_PATH.exists():
        return []
    with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: List[Dict[str, Any]]) -> None:
    with open(TASK_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)