import json
import logging
from pathlib import Path
from typing import List, Dict, Any

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
logger = logging.getLogger(__name__)


def load_registry() -> List[Dict[str, Any]]:
    if not TASK_REGISTRY_PATH.exists():
        return []
    with open(TASK_REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_registry(registry: List[Dict[str, Any]]) -> None:
    with open(TASK_REGISTRY_PATH, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def update_task_status(task_id: str, status: str, comment: str) -> bool:
    registry = load_registry()
    for task in registry:
        if task["id"] == task_id:
            task["status"] = status
            task["updated_at"] = __import__("datetime").datetime.now().isoformat()
            task["history"].append({
                "timestamp": __import__("datetime").datetime.now().isoformat(),
                "from": task.get("status", "NEW"),
                "to": status,
                "actor": "integrator",
                "comment": comment
            })
            save_registry(registry)
            return True
    return False