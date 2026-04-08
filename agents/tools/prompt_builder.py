#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prompt_builder.py – сервис выдачи промптов с контролем целостности.
Используется агентами для получения актуальных системных инструкций.
Версия 1.0 (Золотой стандарт 5.0)
Особенности:
- Проверка целостности через SHA256 хеши
- Отслеживание изменений через mtime (время модификации файла)
- Автоматическое обновление хешей при изменении файлов
- Логирование в локальный файл и отправка в BR18 (Log Aggregator)
- Пассивный режим (без Git-зависимостей)
"""

import os
import json
import hashlib
import logging
import time
import httpx
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Настройки
PROMPT_DIR = Path("00_КАНОН/ПРОМПТЫ")
HASH_FILE = PROMPT_DIR / "prompt_hashes.json"
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/prompt_access.log")
BR18_ENDPOINT = "http://log-aggregator:8093/api/logs"

# Создаём директорию для логов, если её нет
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# Настройка логирования
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_file_mtime(file_path: Path) -> float:
    """Возвращает время последней модификации файла в секундах с эпохи."""
    return file_path.stat().st_mtime

def compute_hash(file_path: Path) -> str:
    """Вычисляет SHA256 хеш файла."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

def load_hashes() -> Dict[str, Any]:
    """Загружает эталонные хеши из JSON-файла. Если файла нет – возвращает пустой словарь."""
    if HASH_FILE.exists():
        with open(HASH_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_hashes(hashes: Dict[str, Any]) -> None:
    """Сохраняет эталонные хеши в JSON-файл."""
    with open(HASH_FILE, "w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, ensure_ascii=False)

def init_hashes() -> Dict[str, Any]:
    """Инициализирует хеши для всех существующих .md файлов промптов."""
    hashes = {}
    for md_file in PROMPT_DIR.glob("*.md"):
        if md_file.name == "prompt_hashes.json":
            continue
        role_name = md_file.stem
        hashes[role_name] = {
            "hash": compute_hash(md_file),
            "mtime": get_file_mtime(md_file),
            "last_verified": datetime.now().isoformat()
        }
    save_hashes(hashes)
    logging.info(f"Initialized prompt hashes for {len(hashes)} roles")
    send_log_to_br18("prompt_hashes_initialized", {"count": len(hashes)})
    return hashes

def send_log_to_br18(event_type: str, details: Dict[str, Any]) -> None:
    """
    Отправляет лог в BR18 (Log Aggregator).
    Работает асинхронно в фоновом режиме, не блокирует основной поток.
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "C7.1",
        "event_type": event_type,
        "details": details
    }
    
    try:
        # Асинхронная отправка через httpx
        import threading
        def send_async():
            try:
                httpx.post(BR18_ENDPOINT, json=log_entry, timeout=2.0)
            except Exception as e:
                # Если BR18 недоступен, просто логируем локально
                logging.warning(f"Failed to send log to BR18: {e}")
        
        thread = threading.Thread(target=send_async)
        thread.daemon = True
        thread.start()
    except Exception as e:
        logging.warning(f"Failed to create thread for BR18 logging: {e}")

def get_prompt(role: str) -> Optional[str]:
    """
    Возвращает текст промпта для указанной роли, проверяя целостность.
    Автоматически обновляет хеш при изменении файла (по mtime).
    При несовпадении хеша возвращает None и логирует ошибку.
    """
    prompt_file = PROMPT_DIR / f"{role}.md"
    if not prompt_file.exists():
        logging.error(f"Prompt file for role {role} not found")
        send_log_to_br18("prompt_file_not_found", {"role": role})
        return None

    # Получаем текущие метаданные файла
    current_mtime = get_file_mtime(prompt_file)
    current_hash = compute_hash(prompt_file)

    # Загружаем эталонные хеши
    hashes = load_hashes()

    # Если эталонов нет – инициализируем их
    if not hashes:
        hashes = init_hashes()

    # Проверяем, есть ли эталон для этой роли
    if role not in hashes:
        logging.error(f"No reference hash for role {role}")
        send_log_to_br18("prompt_hash_missing", {"role": role})
        return None

    # Проверяем, изменился ли файл (по mtime)
    stored_mtime = hashes[role].get("mtime")
    if stored_mtime is None or abs(stored_mtime - current_mtime) > 0.001:
        # Файл изменился - обновляем хеш
        hashes[role] = {
            "hash": current_hash,
            "mtime": current_mtime,
            "last_verified": datetime.now().isoformat()
        }
        save_hashes(hashes)
        logging.info(f"Updated hash for role {role} (file changed)")
        send_log_to_br18("prompt_file_changed", {
            "role": role,
            "old_mtime": stored_mtime,
            "new_mtime": current_mtime
        })
    else:
        # Файл не менялся - проверяем хеш
        if hashes[role]["hash"] != current_hash:
            logging.warning(f"Hash mismatch for role {role}. Prompt may have been altered.")
            send_log_to_br18("prompt_hash_mismatch", {
                "role": role,
                "expected": hashes[role]["hash"],
                "actual": current_hash
            })
            return None

    # Хеши совпадают – возвращаем содержимое
    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()

    logging.info(f"Prompt for role {role} served successfully")
    send_log_to_br18("prompt_accessed", {"role": role})
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
