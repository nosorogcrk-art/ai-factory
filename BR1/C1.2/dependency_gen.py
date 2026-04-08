#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
dependency_gen.py – автоматическое определение зависимостей между патчами.
"""

import json
import re
import logging
from pathlib import Path
from collections import defaultdict
from typing import List, Dict, Any

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
GRAPH_PATH = Path("00_ПАМЯТЬ/ГРАФЫ/GRAPH_DEPENDENCIES.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/dependency_gen.log")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_json(path: Path, default: Any = None) -> Any:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(path: Path, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_ids(text: str) -> List[str]:
    """Извлекает из текста все подстроки, похожие на ID патчей (например, IMP-20250317-001)."""
    pattern = r'\b(?:IMP-\d{8}-\d{3}|P\d+\.\d+\.\d+)\b'
    return re.findall(pattern, text)


def build_skill_dependencies(tasks: List[Dict[str, Any]]) -> List[tuple[str, str]]:
    """Строит зависимости на основе навыков (required_skills и modified_skills)."""
    required = defaultdict(list)
    modified = defaultdict(list)
    for task in tasks:
        tid = task["id"]
        for skill in task.get("required_skills", []):
            required[skill].append(tid)
        for skill in task.get("modified_skills", []):
            modified[skill].append(tid)
    new_edges = []
    for skill, req_list in required.items():
        mod_list = modified.get(skill, [])
        for req in req_list:
            for mod in mod_list:
                if req != mod:
                    new_edges.append((req, mod))
    return new_edges


def main() -> None:
    registry = load_json(TASK_REGISTRY_PATH, [])
    graph = load_json(GRAPH_PATH, {"nodes": [], "edges": []})

    # Собираем все существующие ID
    existing_ids = {task["id"] for task in registry if "id" in task}

    # Добавляем все ID как узлы (если их нет)
    for task in registry:
        tid = task["id"]
        if tid not in [n["id"] for n in graph["nodes"]]:
            graph["nodes"].append({"id": tid, "label": task.get("title", tid), "type": "patch"})

    # Сканируем описания задач на наличие ссылок
    edges_added = 0
    for task in registry:
        from_id = task["id"]
        text = task.get("description", "") + " " + task.get("title", "")
        found_ids = extract_ids(text)
        for to_id in found_ids:
            if to_id in existing_ids and to_id != from_id:
                # Проверяем, не существует ли уже такое ребро
                edge_exists = any(e["from"] == from_id and e["to"] == to_id for e in graph["edges"])
                if not edge_exists:
                    graph["edges"].append({"from": from_id, "to": to_id})
                    edges_added += 1
                    logger.info(f"Added dependency (explicit): {from_id} -> {to_id}")

    # Добавляем зависимости на основе навыков
    skill_edges = build_skill_dependencies(registry)
    for from_id, to_id in skill_edges:
        edge_exists = any(e["from"] == from_id and e["to"] == to_id for e in graph["edges"])
        if not edge_exists:
            graph["edges"].append({"from": from_id, "to": to_id})
            edges_added += 1
            logger.info(f"Added dependency (skill): {from_id} -> {to_id}")

    save_json(GRAPH_PATH, graph)
    result = {"status": "ok", "edges_added": edges_added}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()