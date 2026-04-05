#!/usr/bin/env python3
import json
import os
from datetime import datetime

REGISTRY_FILE = "SYSTEM_REGISTRY.json"

EXPECTED_DIRS = {
    "00_КАНОН/01_РОЛИ": {"expected": True, "permissions": "755", "type": "canon"},
    "00_КАНОН/02_ПРАВИЛА": {"expected": True, "permissions": "755", "type": "canon"},
    "01_ЦЕХ/01_ЖУРНАЛЫ": {"expected": True, "permissions": "775", "type": "workshop"},
    "01_ЦЕХ/01_ЖУРНАЛЫ/АРГУС_ВХОД": {"expected": True, "permissions": "775", "type": "workshop"},
    "01_ЦЕХ/02_ЧЕРНОВИКИ": {"expected": True, "permissions": "775", "type": "workshop"},
    "01_ЦЕХ/03_СБОРКИ": {"expected": True, "permissions": "775", "type": "workshop"},
    "01_ЦЕХ/04_ЗАДАЧИ": {"expected": True, "permissions": "775", "type": "workshop"},
    "01_ЦЕХ/05_КАРАНТИН": {"expected": True, "permissions": "775", "type": "workshop"},
    "02_ПРОДУКТ/01_КОД": {"expected": True, "permissions": "775", "type": "product"},
    "02_ПРОДУКТ/02_ДОКИ": {"expected": True, "permissions": "775", "type": "product"},
    "data": {"expected": True, "permissions": "775", "type": "data"}
}

def init_registry():
    if os.path.exists(REGISTRY_FILE):
        print(f"ℹ️  Файл {REGISTRY_FILE} уже существует. Пропускаем.")
        return

    registry = {
        "registry_version": "1.0",
        "last_update": datetime.now().isoformat(),
        "directories": {},
        "branches": {}
    }

    for path, attrs in EXPECTED_DIRS.items():
        registry["directories"][path] = {
            "expected": attrs["expected"],
            "permissions": attrs["permissions"],
            "type": attrs["type"]
        }

    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)

    print(f"✅ Файл {REGISTRY_FILE} создан с полной структурой.")

if __name__ == "__main__":
    init_registry()
