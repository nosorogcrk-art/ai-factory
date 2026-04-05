#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate_task_model.py – генерация модели переходов на основе pipeline_config.json.
Выполняет слияние с существующей моделью, логирует изменения.
"""

import json
import logging
from pathlib import Path

PIPELINE_CONFIG = Path("00_КАНОН/Методология/pipeline_config.json")
TASK_MODEL_PATH = Path("00_КАНОН/ПРОЦЕССЫ/task_model.json")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/generate_task_model.log")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_json(path, default=None):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_pipeline():
    if not PIPELINE_CONFIG.exists():
        raise FileNotFoundError(f"Pipeline config not found: {PIPELINE_CONFIG}")
    with open(PIPELINE_CONFIG, "r", encoding="utf-8") as f:
        return json.load(f)

def generate_transitions(stages):
    """Генерирует переходы по умолчанию из последовательности этапов."""
    transitions = []
    for i in range(len(stages)-1):
        transitions.append({
            "from": stages[i]["id"],
            "to": stages[i+1]["id"],
            "allowed_roles": stages[i+1].get("allowed_roles", [])
        })
    # Стандартные служебные переходы
    transitions.append({
        "from": "*",
        "to": "BLOCKED",
        "allowed_roles": ["АРГУС", "*"]
    })
    transitions.append({
        "from": "BLOCKED",
        "to": "NEW",
        "allowed_roles": ["АРГУС"]
    })
    # Переход из REWORK – по умолчанию в L6_CODE, но если есть история, можно уточнить
    transitions.append({
        "from": "REWORK",
        "to": "L6_CODE",
        "allowed_roles": ["ГЕФЕСТ"]
    })
    return transitions

def merge_models(existing, new_statuses, new_transitions):
    """
    Объединяет существующую модель с новыми статусами и переходами.
    - Добавляет недостающие статусы.
    - Добавляет переходы, которых ещё нет (сравнение по полям from, to, allowed_roles).
    """
    if not existing:
        return {"statuses": new_statuses, "transitions": new_transitions}

    merged = existing.copy()
    # Статусы
    existing_statuses = set(merged.get("statuses", []))
    for s in new_statuses:
        if s not in existing_statuses:
            merged["statuses"].append(s)
            logging.info(f"Added status: {s}")

    # Переходы
    existing_transitions = merged.get("transitions", [])
    # Для удобства создадим множество кортежей (from, to, frozenset(allowed_roles))
    def key(t):
        return (t["from"], t["to"], frozenset(t.get("allowed_roles", [])))
    existing_keys = {key(t) for t in existing_transitions}

    for t in new_transitions:
        if key(t) not in existing_keys:
            existing_transitions.append(t)
            logging.info(f"Added transition: {t['from']} -> {t['to']} (roles: {t.get('allowed_roles', [])})")
            existing_keys.add(key(t))

    merged["transitions"] = existing_transitions
    return merged

def main():
    try:
        pipeline = load_pipeline()
    except FileNotFoundError as e:
        logging.error(e)
        print(f"❌ {e}")
        return

    stages = pipeline["stages"]
    new_statuses = [stage["id"] for stage in stages]
    # Добавляем служебные статусы, если их нет
    for s in ["BLOCKED", "REWORK"]:
        if s not in new_statuses:
            new_statuses.append(s)

    new_transitions = generate_transitions(stages)

    existing_model = load_json(TASK_MODEL_PATH)
    merged_model = merge_models(existing_model, new_statuses, new_transitions)

    save_json(TASK_MODEL_PATH, merged_model)
    logging.info(f"Task model saved to {TASK_MODEL_PATH}")
    print(f"✅ Task model generated and saved to {TASK_MODEL_PATH}")

if __name__ == "__main__":
    main()
