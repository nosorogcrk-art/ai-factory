#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prompt_builder.py – сервис выдачи промптов с контролем целостности.
Используется агентами для получения актуальных системных инструкций.
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from datetime import datetime

# Настройки
PROMPT_DIR = Path("00_КАНОН/ПРОМПТЫ")
HASH_FILE = PROMPT_DIR / "prompt_hashes.json"
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/prompt_access.log")

# Создаём директорию для логов, если её нет
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def compute_hash(file_path):
    """Вычисляет SHA256 хеш файла."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_hashes():
    """Загружает эталонные хеши из JSON-файла. Если файла нет – возвращает пустой словарь."""
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_hashes(hashes):
    """Сохраняет эталонные хеши в JSON-файл."""
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)

def init_hashes():
    """Инициализирует хеши для всех существующих .md файлов промптов."""
    hashes = {}
    for md_file in PROMPT_DIR.glob("*.md"):
        if md_file.name == "prompt_hashes.json":
            continue
        role_name = md_file.stem
        hashes[role_name] = {
            "hash": compute_hash(md_file),
            "last_verified": datetime.now().isoformat()
        }
    save_hashes(hashes)
    logging.info(f"Initialized prompt hashes for {len(hashes)} roles")
    return hashes

def get_prompt(role):
    """
    Возвращает текст промпта для указанной роли, проверяя целостность.
    При несовпадении хеша возвращает None и логирует ошибку.
    """
    prompt_file = PROMPT_DIR / f"{role}.md"
    if not prompt_file.exists():
        logging.error(f"Prompt file for role {role} not found")
        return None

    # Вычисляем текущий хеш
    current_hash = compute_hash(prompt_file)

    # Загружаем эталонные хеши
    hashes = load_hashes()

    # Если эталонов нет – инициализируем их
    if not hashes:
        hashes = init_hashes()

    # Проверяем, есть ли эталон для этой роли
    if role not in hashes:
        logging.error(f"No reference hash for role {role}")
        return None

    # Сравниваем хеши
    if hashes[role]["hash"] != current_hash:
        logging.warning(f"Hash mismatch for role {role}. Prompt may have been altered.")
        return None

    # Хеши совпадают – возвращаем содержимое
    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()

    logging.info(f"Prompt for role {role} served successfully")
    return content

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python prompt_builder.py <ROLE>")
        sys.exit(1)
    role = sys.argv[1].upper()
    prompt = get_prompt(role)
    if prompt:
        print(prompt)
    else:
        print(f"Failed to get prompt for role {role}", file=sys.stderr)
        sys.exit(1)
