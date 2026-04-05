#!/usr/bin/env python3
"""
Модуль сканера для C0.2 Reality Observer.
Обеспечивает fast_scan и deep_scan файловой системы с проверкой
соответствия SYSTEM_REGISTRY.json.
"""

import json
import hashlib
import logging
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime

# Импорт модуля карантина
from quarantine import move_to_quarantine

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы
REGISTRY_PATH = Path("SYSTEM_REGISTRY.json")
EXCLUDE_DIRS = {".git", "__pycache__", ".DS_Store", "node_modules", ".venv"}
EXCLUDE_EXTENSIONS = {".tmp", ".log", ".cache"}

def load_registry() -> Dict:
    """Загружает SYSTEM_REGISTRY.json."""
    if not REGISTRY_PATH.exists():
        logger.error(f"Реестр не найден: {REGISTRY_PATH}")
        return {}
    
    try:
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке реестра: {e}")
        return {}

def get_registered_paths(registry: Dict) -> Set[Path]:
    """Возвращает множество зарегистрированных путей из реестра."""
    registered = set()
    
    # Добавляем файлы
    for file_path in registry.get("files", []):
        registered.add(Path(file_path))
    
    # Добавляем директории и их содержимое
    for dir_path in registry.get("directories", []):
        dir_path_obj = Path(dir_path)
        if dir_path_obj.exists() and dir_path_obj.is_dir():
            registered.add(dir_path_obj)
            # Рекурсивно добавляем все файлы в директории
            for file in dir_path_obj.rglob("*"):
                if file.is_file():
                    registered.add(file)
    
    return registered

def calculate_file_hash(file_path: Path) -> str:
    """Вычисляет SHA-256 хэш файла."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception as e:
        logger.error(f"Ошибка при вычислении хэша {file_path}: {e}")
        return ""

def should_skip_path(path: Path) -> bool:
    """Определяет, нужно ли пропускать путь при сканировании."""
    # Пропускаем скрытые файлы и системные директории
    if any(part.startswith('.') for part in path.parts):
        return True
    
    # Пропускаем исключённые директории
    if any(excluded in path.parts for excluded in EXCLUDE_DIRS):
        return True
    
    # Пропускаем исключённые расширения
    if path.suffix in EXCLUDE_EXTENSIONS:
        return True
    
    return False

def fast_scan() -> Tuple[List[Path], List[Path]]:
    """
    Быстрое сканирование - проверяет только зарегистрированные файлы.
    
    Returns:
        Tuple[List[Path], List[Path]]: (отсутствующие файлы, новые файлы)
    """
    logger.info("Запуск fast_scan...")
    
    registry = load_registry()
    if not registry:
        return [], []
    
    registered_paths = get_registered_paths(registry)
    missing_files = []
    new_files = []
    
    # Проверяем зарегистрированные файлы
    for path in registered_paths:
        if path.is_file() and not path.exists():
            missing_files.append(path)
            logger.warning(f"Отсутствует зарегистрированный файл: {path}")
    
    # Для fast_scan не ищем новые файлы (только проверяем существующие)
    # Новые файлы будут обнаружены в deep_scan
    
    logger.info(f"Fast_scan завершён. Отсутствует файлов: {len(missing_files)}")
    return missing_files, new_files

def deep_scan() -> Tuple[List[Path], List[Path]]:
    """
    Глубокое сканирование - проверяет всю файловую систему.
    
    Returns:
        Tuple[List[Path], List[Path]]: (отсутствующие файлы, незарегистрированные файлы)
    """
    logger.info("Запуск deep_scan...")
    
    registry = load_registry()
    if not registry:
        return [], []
    
    registered_paths = get_registered_paths(registry)
    missing_files = []
    unregistered_files = []
    
    # Проверяем зарегистрированные файлы
    for path in registered_paths:
        if path.is_file() and not path.exists():
            missing_files.append(path)
            logger.warning(f"Отсутствует зарегистрированный файл: {path}")
    
    # Сканируем всю файловую систему начиная с текущей директории
    scan_root = Path.cwd()
    
    for file_path in scan_root.rglob("*"):
        if not file_path.is_file() or should_skip_path(file_path):
            continue
        
        # Проверяем, зарегистрирован ли файл
        if file_path not in registered_paths:
            # Проверяем, находится ли файл в зарегистрированной директории
            in_registered_dir = False
            for registered_path in registered_paths:
                if registered_path.is_dir() and file_path.is_relative_to(registered_path):
                    in_registered_dir = True
                    break
            
            if not in_registered_dir:
                unregistered_files.append(file_path)
                logger.info(f"Обнаружен незарегистрированный файл: {file_path}")
    
    logger.info(f"Deep_scan завершён. Отсутствует: {len(missing_files)}, Незарегистрировано: {len(unregistered_files)}")
    return missing_files, unregistered_files

def quarantine_unregistered_files(unregistered_files: List[Path]) -> List[Path]:
    """
    Перемещает незарегистрированные файлы в карантин.
    
    Returns:
        List[Path]: Список успешно помещённых в карантин файлов
    """
    quarantined = []
    
    for file_path in unregistered_files:
        result = move_to_quarantine(file_path, "unregistered")
        if result:
            quarantined.append(result)
    
    return quarantined

def generate_reality_snapshot() -> Dict:
    """
    Генерирует снимок реальности системы.
    
    Returns:
        Dict: Снимок с информацией о состоянии системы
    """
    registry = load_registry()
    missing_files, unregistered_files = deep_scan()
    
    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "registry_loaded": bool(registry),
        "registered_files_count": len(registry.get("files", [])),
        "registered_dirs_count": len(registry.get("directories", [])),
        "missing_files": [str(p) for p in missing_files],
        "unregistered_files": [str(p) for p in unregistered_files],
        "quarantine_action": "pending"
    }
    
    # Если есть незарегистрированные файлы, перемещаем их в карантин
    if unregistered_files:
        quarantined = quarantine_unregistered_files(unregistered_files)
        snapshot["quarantined_files"] = [str(p) for p in quarantined]
        snapshot["quarantine_action"] = "executed"
        snapshot["quarantined_count"] = len(quarantined)
    
    # Сохраняем снимок
    snapshot_path = Path("REALITY_SNAPSHOT.json")
    with open(snapshot_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Снимок реальности сохранён: {snapshot_path}")
    return snapshot

if __name__ == "__main__":
    # Тестирование модуля
    print("Тестирование модуля сканера...")
    
    # Запускаем deep_scan
    missing, unregistered = deep_scan()
    
    print(f"Отсутствующие файлы: {len(missing)}")
    print(f"Незарегистрированные файлы: {len(unregistered)}")
    
    # Генерируем снимок
    snapshot = generate_reality_snapshot()
    print(f"Снимок сгенерирован: {snapshot['timestamp']}")
    
    # Запускаем fast_scan
    missing_fast, _ = fast_scan()
    print(f"Fast_scan: отсутствует файлов: {len(missing_fast)}")
