import sqlite3
import os
import uuid
from datetime import datetime
from typing import List, Optional, Tuple
from contextlib import contextmanager

from app.models.deployment import (
    DeploymentCreate, DeploymentResponse, DeploymentStatus,
    RollbackStatus, RollbackHistoryResponse
)


class DeploymentRepository:
    """Репозиторий для работы с историей деплоев и откатов"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Инициализация репозитория с указанием пути к БД"""
        if db_path is None:
            # По умолчанию используем /data/rollback_history.db в Docker или локальный файл
            if os.path.exists("/data"):
                self.db_path = "/data/rollback_history.db"
            else:
                # Для локальной разработки и тестов
                self.db_path = "rollback_history.db"
        else:
            self.db_path = db_path
        
        # Создаем директорию для базы данных если она не существует
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        self._init_db()
    
    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для получения соединения с БД"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def _init_db(self) -> None:
        """Инициализация базы данных, создание таблиц если их нет"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица для хранения истории деплоев
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deployments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    deploy_id TEXT NOT NULL UNIQUE,
                    repository TEXT NOT NULL,
                    commit_hash TEXT NOT NULL,
                    tag TEXT,
                    environment TEXT NOT NULL,
                    config_files TEXT NOT NULL,  -- JSON список файлов
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'success',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица для хранения истории откатов
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rollbacks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    rollback_id TEXT NOT NULL UNIQUE,
                    deploy_id TEXT NOT NULL,
                    target_version TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (deploy_id) REFERENCES deployments(deploy_id)
                )
            """)
            
            # Индексы для быстрого поиска
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deploy_id ON deployments(deploy_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deployments_created_at ON deployments(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_deployments_environment ON deployments(environment)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rollbacks_rollback_id ON rollbacks(rollback_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rollbacks_deploy_id ON rollbacks(deploy_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_rollbacks_status ON rollbacks(status)")
            
            conn.commit()
    
    def save_deployment(self, deployment: DeploymentCreate) -> int:
        """
        Сохранение информации о деплое
        
        Args:
            deployment: Данные о деплое
            
        Returns:
            ID сохраненной записи
            
        Raises:
            ValueError: Если deploy_id уже существует
        """
        # Проверка на существование deploy_id
        existing = self.get_deployment_by_id(deployment.deploy_id)
        if existing:
            raise ValueError(f"Deploy ID {deployment.deploy_id} already exists")
        
        # Преобразование списка файлов в JSON строку
        import json
        config_files_json = json.dumps(deployment.config_files)
        
        # Используем текущее время с микросекундами
        current_time = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO deployments 
                (deploy_id, repository, commit_hash, tag, environment, 
                 config_files, description, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deployment.deploy_id,
                deployment.repository,
                deployment.commit_hash,
                deployment.tag,
                deployment.environment,
                config_files_json,
                deployment.description,
                DeploymentStatus.SUCCESS.value,
                current_time
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_deployment_by_id(self, deploy_id: str) -> Optional[DeploymentResponse]:
        """Получение информации о деплое по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, deploy_id, repository, commit_hash, tag, environment,
                       config_files, description, status, created_at
                FROM deployments 
                WHERE deploy_id = ?
            """, (deploy_id,))
            
            row = cursor.fetchone()
            if row:
                import json
                return DeploymentResponse(
                    id=row['id'],
                    deploy_id=row['deploy_id'],
                    repository=row['repository'],
                    commit_hash=row['commit_hash'],
                    tag=row['tag'],
                    environment=row['environment'],
                    config_files=json.loads(row['config_files']),
                    description=row['description'],
                    status=DeploymentStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at'])
                )
            return None
    
    def get_deployments(self, limit: int = 100, offset: int = 0, 
                       environment: Optional[str] = None) -> List[DeploymentResponse]:
        """Получение списка деплоев"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT id, deploy_id, repository, commit_hash, tag, environment,
                       config_files, description, status, created_at
                FROM deployments 
            """
            params = []
            
            if environment:
                query += " WHERE environment = ?"
                params.append(environment)
            
            query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            import json
            return [
                DeploymentResponse(
                    id=row['id'],
                    deploy_id=row['deploy_id'],
                    repository=row['repository'],
                    commit_hash=row['commit_hash'],
                    tag=row['tag'],
                    environment=row['environment'],
                    config_files=json.loads(row['config_files']),
                    description=row['description'],
                    status=DeploymentStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at'])
                )
                for row in rows
            ]
    
    def get_latest_deployment(self, environment: Optional[str] = None) -> Optional[DeploymentResponse]:
        """Получение последнего деплоя"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT id, deploy_id, repository, commit_hash, tag, environment,
                       config_files, description, status, created_at
                FROM deployments 
            """
            params = []
            
            if environment:
                query += " WHERE environment = ?"
                params.append(environment)
            
            query += " ORDER BY created_at DESC LIMIT 1"
            
            cursor.execute(query, params)
            row = cursor.fetchone()
            
            if row:
                import json
                return DeploymentResponse(
                    id=row['id'],
                    deploy_id=row['deploy_id'],
                    repository=row['repository'],
                    commit_hash=row['commit_hash'],
                    tag=row['tag'],
                    environment=row['environment'],
                    config_files=json.loads(row['config_files']),
                    description=row['description'],
                    status=DeploymentStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at'])
                )
            return None
    
    def get_previous_deployment(self, deploy_id: str) -> Optional[DeploymentResponse]:
        """Получение предыдущего деплоя относительно указанного"""
        current = self.get_deployment_by_id(deploy_id)
        if not current:
            return None
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Получаем все деплои в том же окружении, отсортированные по времени
            cursor.execute("""
                SELECT id, deploy_id, repository, commit_hash, tag, environment,
                       config_files, description, status, created_at
                FROM deployments 
                WHERE environment = ?
                ORDER BY created_at DESC, id DESC
            """, (current.environment,))
            
            rows = cursor.fetchall()
            
            # Находим текущий деплой в списке и берем следующий за ним
            found_current = False
            for row in rows:
                if row['deploy_id'] == deploy_id:
                    found_current = True
                elif found_current:
                    # Это предыдущий деплой
                    import json
                    return DeploymentResponse(
                        id=row['id'],
                        deploy_id=row['deploy_id'],
                        repository=row['repository'],
                        commit_hash=row['commit_hash'],
                        tag=row['tag'],
                        environment=row['environment'],
                        config_files=json.loads(row['config_files']),
                        description=row['description'],
                        status=DeploymentStatus(row['status']),
                        created_at=datetime.fromisoformat(row['created_at'])
                    )
            
            return None
    
    def create_rollback(self, deploy_id: str, target_version: str, reason: str) -> str:
        """
        Создание записи об откате
        
        Args:
            deploy_id: ID деплоя для отката
            target_version: Целевая версия для отката
            reason: Причина отката
            
        Returns:
            ID созданного отката
        """
        rollback_id = f"rb_{uuid.uuid4().hex[:8]}"
        
        # Используем текущее время с микросекундами
        current_time = datetime.now().isoformat()
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO rollbacks 
                (rollback_id, deploy_id, target_version, reason, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                rollback_id,
                deploy_id,
                target_version,
                reason,
                RollbackStatus.PENDING.value,
                current_time
            ))
            
            conn.commit()
            return rollback_id
    
    def update_rollback_status(self, rollback_id: str, status: RollbackStatus, 
                             completed: bool = False) -> bool:
        """
        Обновление статуса отката
        
        Args:
            rollback_id: ID отката
            status: Новый статус
            completed: Завершен ли откат
            
        Returns:
            True если обновлено, False если не найдено
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if completed:
                cursor.execute("""
                    UPDATE rollbacks 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE rollback_id = ?
                """, (status.value, rollback_id))
            else:
                cursor.execute("""
                    UPDATE rollbacks 
                    SET status = ?
                    WHERE rollback_id = ?
                """, (status.value, rollback_id))
            
            conn.commit()
            return cursor.rowcount > 0
    
    def get_rollback_by_id(self, rollback_id: str) -> Optional[RollbackHistoryResponse]:
        """Получение информации об откате по ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, rollback_id, deploy_id, target_version, reason,
                       status, created_at, completed_at
                FROM rollbacks 
                WHERE rollback_id = ?
            """, (rollback_id,))
            
            row = cursor.fetchone()
            if row:
                return RollbackHistoryResponse(
                    id=row['id'],
                    rollback_id=row['rollback_id'],
                    deploy_id=row['deploy_id'],
                    target_version=row['target_version'],
                    reason=row['reason'],
                    status=RollbackStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
                )
            return None
    
    def get_rollbacks(self, limit: int = 100, offset: int = 0) -> List[RollbackHistoryResponse]:
        """Получение списка откатов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, rollback_id, deploy_id, target_version, reason,
                       status, created_at, completed_at
                FROM rollbacks 
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            """, (limit, offset))
            
            rows = cursor.fetchall()
            return [
                RollbackHistoryResponse(
                    id=row['id'],
                    rollback_id=row['rollback_id'],
                    deploy_id=row['deploy_id'],
                    target_version=row['target_version'],
                    reason=row['reason'],
                    status=RollbackStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None
                )
                for row in rows
            ]
    
    def get_deployment_count(self) -> int:
        """Получение общего количества деплоев"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM deployments")
            return cursor.fetchone()[0]
    
    def get_rollback_count(self) -> int:
        """Получение общего количества откатов"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rollbacks")
            return cursor.fetchone()[0]
    
    def health_check(self) -> bool:
        """Проверка здоровья базы данных"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                return True
        except Exception:
            return False