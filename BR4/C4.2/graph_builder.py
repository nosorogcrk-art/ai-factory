#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
graph_builder.py – сканирует документы в 00_КАНОН/ и 01_ЦЕХ/,
извлекает ссылки [[ID]] и строит JSON-граф (узлы, рёбра).
Сохраняет результат в 01_ЦЕХ/ГРАФ/links_graph.json.
"""

import json
import re
import logging
import os
from pathlib import Path

# Директории для сканирования
SCAN_DIRS = [
    Path("00_КАНОН"),
    Path("01_ЦЕХ")
]
OUTPUT_FILE = Path("01_ЦЕХ/ГРАФ/links_graph.json")
TASK_REGISTRY = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/graph_builder.log")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

IGNORE_DIRS = {".git", "__pycache__", ".DS_Store"}

def load_task_ids():
    """Загружает ID задач из реестра (если есть) для пометки узлов."""
    if not TASK_REGISTRY.exists():
        return set()
    try:
        with open(TASK_REGISTRY, "r", encoding="utf-8") as f:
            tasks = json.load(f)
        return {t["id"] for t in tasks}
    except Exception as e:
        logging.error(f"Failed to load task registry: {e}")
        return set()

def extract_links(content):
    """Извлекает все ссылки вида [[ID]] из текста."""
    pattern = re.compile(r'\[\[([A-Z0-9\-_]+)\]\]')
    return pattern.findall(content)

def build_graph():
    task_ids = load_task_ids()
    nodes = set()
    edges = []

    for scan_dir in SCAN_DIRS:
        if not scan_dir.exists():
            logging.warning(f"Directory not found: {scan_dir}")
            continue
        for root, dirs, files in os.walk(scan_dir):
            # Исключаем служебные папки
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
            for file in files:
                if not file.endswith(".md"):
                    continue
                file_path = Path(root) / file
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except Exception as e:
                    logging.error(f"Error reading {file_path}: {e}")
                    continue

                # Узел для текущего документа
                doc_id = str(file_path)
                nodes.add(doc_id)

                links = extract_links(content)
                for link in links:
                    nodes.add(link)
                    edges.append({"source": doc_id, "target": link})

    # Преобразуем узлы в список с типом
    node_list = []
    for n in nodes:
        node_type = "task" if n in task_ids else "doc"
        node_list.append({"id": n, "label": n, "type": node_type})

    graph = {"nodes": node_list, "edges": edges}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2, ensure_ascii=False)
    logging.info(f"Graph saved to {OUTPUT_FILE}, nodes: {len(node_list)}, edges: {len(edges)}")
    print(f"Graph saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    build_graph()
