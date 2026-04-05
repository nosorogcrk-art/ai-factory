#!/usr/bin/env python3
"""
Модуль карантина для C0.2 Reality Observer.
Обеспечивает перемещение незарегистрированных файлов в карантин,
обновление SYSTEM_REGISTRY.json и отправку уведомлений в BR18.
"""

import json
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
import httpx
from typing import Dict, List, Optional

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Константы
QUARANTINE_DIR = Path("01_ЦЕХ/05_КАРАНТИН")
REGISTRY_PATH = Path("SYSTEM_REGISTRY.json")
BR18_URL = "http://br18:8098"  # URL для отправки уведомлений в BR18

def ensure_quarantine_dir() -> Path:
    """Создаёт карантинную директорию, если её нет."""
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    return QUARANTINE_DIR

def move_to_quarantine(file_path: Path, reason: str = "unregistered") -> Optional[Path]:
    """
    Перемещает файл в карантин и обновляет реестр.
    
    Args:
        file_path: Путь к файлу для карантина
        reason: Причина карантина (unregistered, suspicious, etc.)
    
    Returns:
        Path: Новый путь в карантине или None при ошибке
    """
    try:
        if not file_path.exists():
            logger.warning(f"Файл не существует: {file_path}")
            return None
        
        # Создаём уникальное имя для файла в карантине
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        original_name = file_path.name
        quarantine_name = f"{timestamp}_{original_name}"
        quarantine_path = ensure_quarantine_dir() / quarantine_name
        
        # Перемещаем файл
        shutil.move(str(file_path), str(quarantine_path))
        logger.info(f"Файл перемещён в карантин: {file_path} -> {quarantine_path}")
        
        # Обновляем реестр
        update_registry(file_path, quarantine_path, reason)
        
        # Отправляем уведомление в BR18
        send_message_to_argus(
            f"Файл помещён в карантин: {file_path}",
            level="warning",
            metadata={
                "original_path": str(file_path),
                "quarantine_path": str(quarantine_path),
                "reason": reason,
                "timestamp": timestamp
            }
        )
        
        return quarantine_path
        
    except Exception as e:
        logger.error(f"Ошибка при перемещении в карантин: {e}")
        return None

def update_registry(original_path: Path, quarantine_path: Path, reason: str):
    """
    Обновляет SYSTEM_REGISTRY.json, добавляя запись о карантине.
    """
    try:
        if not REGISTRY_PATH.exists():
            logger.error(f"Реестр не найден: {REGISTRY_PATH}")
            return
        
        with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
            registry = json.load(f)
        
        # Добавляем запись в раздел quarantined_files
        if "quarantined_files" not in registry:
            registry["quarantined_files"] = []
        
        quarantine_entry = {
            "original_path": str(original_path),
            "quarantine_path": str(quarantine_path),
            "reason": reason,
            "quarantined_at": datetime.now().isoformat(),
            "size": quarantine_path.stat().st_size if quarantine_path.exists() else 0
        }
        
        registry["quarantined_files"].append(quarantine_entry)
        
        # Сохраняем обновлённый реестр
        with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
            json.dump(registry, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Реестр обновлён для файла: {original_path}")
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении реестра: {e}")

def send_message_to_argus(message: str, level: str = "info", metadata: Dict = None):
    """
    Отправляет сообщение в BR18 (Аргус) для логирования.
    
    Args:
        message: Текст сообщения
        level: Уровень важности (info, warning, error)
        metadata: Дополнительные метаданные
    """
    try:
        payload = {
            "message": message,
            "level": level,
            "source": "C0.2",
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }
        
        # В реальной реализации здесь будет HTTP-запрос к BR18
        # Для тестирования просто логируем
        logger.info(f"Сообщение для Аргуса: {message} (уровень: {level})")
        
        # TODO: Раскомментировать когда BR18 будет доступен
        # async with httpx.AsyncClient() as client:
        #     response = await client.post(
        #         f"{BR18_URL}/api/log",
        #         json=payload,
        #         timeout=10.0
        #     )
        #     response.raise_for_status()
            
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения в BR18: {e}")

def clean_old_quarantine_files(days: int = 7) -> List[Path]:
    """
    Удаляет файлы из карантина старше указанного количества дней.
    
    Args:
        days: Количество дней для хранения файлов в карантине
    
    Returns:
        List[Path]: Список удалённых файлов
    """
    try:
        if not QUARANTINE_DIR.exists():
            return []
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_files = []
        
        for file_path in QUARANTINE_DIR.iterdir():
            if file_path.is_file():
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_date:
                    try:
                        file_path.unlink()
                        deleted_files.append(file_path)
                        logger.info(f"Удалён старый файл из карантина: {file_path}")
                    except Exception as e:
                        logger.error(f"Ошибка при удалении файла {file_path}: {e}")
        
        # Обновляем реестр, удаляя записи об удалённых файлах
        if deleted_files and REGISTRY_PATH.exists():
            with open(REGISTRY_PATH, 'r', encoding='utf-8') as f:
                registry = json.load(f)
            
            if "quarantined_files" in registry:
                registry["quarantined_files"] = [
                    entry for entry in registry["quarantined_files"]
                    if Path(entry.get("quarantine_path", "")).exists()
                ]
                
                with open(REGISTRY_PATH, 'w', encoding='utf-8') as f:
                    json.dump(registry, f, indent=2, ensure_ascii=False)
        
        send_message_to_argus(
            f"Очистка карантина: удалено {len(deleted_files)} файлов старше {days} дней",
            level="info",
            metadata={"deleted_count": len(deleted_files), "days": days}
        )
        
        return deleted_files
        
    except Exception as e:
        logger.error(f"Ошибка при очистке карантина: {e}")
        return []

def list_quarantine_files() -> List[Dict]:
    """
    Возвращает список файлов в карантине с метаданными.
    
    Returns:
        List[Dict]: Список файлов с информацией
    """
    try:
        if not QUARANTINE_DIR.exists():
            return []
        
        files = []
        for file_path in QUARANTINE_DIR.iterdir():
            if file_path.is_file():
                stat = file_path.stat()
                files.append({
                    "path": str(file_path),
                    "name": file_path.name,
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "age_days": (datetime.now() - datetime.fromtimestamp(stat.st_mtime)).days
                })
        
        return files
        
    except Exception as e:
        logger.error(f"Ошибка при получении списка файлов в карантине: {e}")
        return []

if __name__ == "__main__":
    # Тестирование модуля
    print("Тестирование модуля карантина...")
    
    # Создаём тестовый файл
    test_file = Path("test_quarantine.txt")
    test_file.write_text("Тестовый файл для карантина")
    
    print(f"Создан тестовый файл: {test_file}")
    
    # Перемещаем в карантин
    result = move_to_quarantine(test_file, "test")
    if result:
        print(f"Файл перемещён в: {result}")
    
    # Список файлов в карантине
    files = list_quarantine_files()
    print(f"Файлов в карантине: {len(files)}")
    
    # Очистка старых файлов (0 дней для теста)
    deleted = clean_old_quarantine_files(days=0)
    print(f"Удалено файлов: {len(deleted)}")