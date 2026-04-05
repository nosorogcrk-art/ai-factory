import hashlib
import sqlite3
import os
from datetime import datetime
from typing import List, Optional, Tuple

from app.models.config import ConfigResponse, ConfigContentResponse


class ConfigRepository:
    """Репозиторий для работы с версиями конфигураций в SQLite"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Инициализация репозитория с указанием пути к БД"""
        if db_path is None:
            # По умолчанию используем /data/config_versions.db в Docker или локальный файл
            if os.path.exists("/data"):
                self.db_path = "/data/config_versions.db"
            else:
                # Для локальной разработки и тестов
                self.db_path = "config_versions.db"
        else:
            self.db_path = db_path
        
        # Создаем директорию для базы данных если она не существует
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self._init_db()
    
    def _init_db(self) -> None:
        """Инициализация базы данных, создание таблиц если их нет"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица для хранения версий конфигураций
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL UNIQUE,
                    config_type TEXT NOT NULL,
                    description TEXT,
                    content TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Индексы для быстрого поиска
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_version ON config_versions(version)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_created_at ON config_versions(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_config_type ON config_versions(config_type)")
            
            conn.commit()
    
    def _calculate_hash(self, content: str) -> str:
        """Вычисление хеша содержимого конфигурации"""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def save_config(self, version: str, config_type: str, content: str, 
                   description: Optional[str] = None) -> int:
        """
        Сохранение новой версии конфигурации
        
        Args:
            version: Версия конфигурации
            config_type: Тип конфигурации
            content: Содержимое конфигурации
            description: Описание изменений
            
        Returns:
            ID сохраненной записи
            
        Raises:
            ValueError: Если версия уже существует
        """
        # Проверка на существование версии
        if self.get_config_by_version(version):
            raise ValueError(f"Версия {version} уже существует")
        
        hash_value = self._calculate_hash(content)
        size_bytes = len(content.encode('utf-8'))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO config_versions 
                (version, config_type, description, content, hash, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (version, config_type, description, content, hash_value, size_bytes))
            
            conn.commit()
            lastrowid = cursor.lastrowid
            if lastrowid is None:
                raise RuntimeError("Не удалось получить ID сохраненной записи")
            return lastrowid
    
    def get_config_by_version(self, version: str) -> Optional[ConfigContentResponse]:
        """Получение конфигурации по версии"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, version, config_type, description, content, 
                       hash, size_bytes, created_at
                FROM config_versions 
                WHERE version = ?
            """, (version,))
            
            row = cursor.fetchone()
            if row:
                return ConfigContentResponse(
                    id=row['id'],
                    version=row['version'],
                    config_type=row['config_type'],
                    description=row['description'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    hash=row['hash'],
                    size_bytes=row['size_bytes']
                )
            return None
    
    def get_config_by_id(self, config_id: int) -> Optional[ConfigContentResponse]:
        """Получение конфигурации по ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, version, config_type, description, content, 
                       hash, size_bytes, created_at
                FROM config_versions 
                WHERE id = ?
            """, (config_id,))
            
            row = cursor.fetchone()
            if row:
                return ConfigContentResponse(
                    id=row['id'],
                    version=row['version'],
                    config_type=row['config_type'],
                    description=row['description'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    hash=row['hash'],
                    size_bytes=row['size_bytes']
                )
            return None
    
    def get_all_configs(self, limit: int = 100, offset: int = 0) -> List[ConfigResponse]:
        """Получение списка всех конфигураций (без содержимого)"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, version, config_type, description, 
                       hash, size_bytes, created_at
                FROM config_versions 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            rows = cursor.fetchall()
            return [
                ConfigResponse(
                    id=row['id'],
                    version=row['version'],
                    config_type=row['config_type'],
                    description=row['description'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    hash=row['hash'],
                    size_bytes=row['size_bytes']
                )
                for row in rows
            ]
    
    def get_config_versions(self) -> List[str]:
        """Получение списка всех версий"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT version FROM config_versions ORDER BY created_at DESC")
            return [row[0] for row in cursor.fetchall()]
    
    def get_latest_config(self) -> Optional[ConfigContentResponse]:
        """Получение последней версии конфигурации"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, version, config_type, description, content, 
                       hash, size_bytes, created_at
                FROM config_versions 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return ConfigContentResponse(
                    id=row['id'],
                    version=row['version'],
                    config_type=row['config_type'],
                    description=row['description'],
                    content=row['content'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    hash=row['hash'],
                    size_bytes=row['size_bytes']
                )
            return None
    
    def delete_config(self, version: str) -> bool:
        """Удаление конфигурации по версии"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM config_versions WHERE version = ?", (version,))
            conn.commit()
            return cursor.rowcount > 0
    
    def get_count(self) -> int:
        """Получение общего количества версий"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM config_versions")
            return cursor.fetchone()[0]
    
    def get_diff(self, from_version: str, to_version: str) -> Optional[Tuple[str, str, int]]:
        """
        Получение разницы между двумя версиями
        
        Returns:
            Tuple[from_content, to_content, changes_count] или None если версии не найдены
        """
        from_config = self.get_config_by_version(from_version)
        to_config = self.get_config_by_version(to_version)
        
        if not from_config or not to_config:
            return None
        
        # Простой подсчет изменений (можно заменить на более сложный алгоритм diff)
        from_lines = set(from_config.content.splitlines())
        to_lines = set(to_config.content.splitlines())
        changes_count = len(from_lines.symmetric_difference(to_lines))
        
        return from_config.content, to_config.content, changes_count
    
    def health_check(self) -> bool:
        """Проверка здоровья базы данных"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False
