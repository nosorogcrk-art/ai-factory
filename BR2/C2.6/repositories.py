import sqlite3
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)

DB_PATH = Path("01_ЦЕХ/ПРОЕКТЫ/projects.db")
PROJECTS_ROOT = Path("01_ЦЕХ/ПРОЕКТЫ")

def init_db():
    """Инициализирует базу данных, создавая таблицы, если они не существуют."""
    conn = sqlite3.connect(DB_PATH)
    try:
        # Таблица проектов
        conn.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_projects_name ON projects(name)')
        
        # Таблица сообщений
        conn.execute('''
            CREATE TABLE IF NOT EXISTS project_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT,
                message_type TEXT DEFAULT 'text',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_project_id ON project_messages(project_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_created_at ON project_messages(created_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON project_messages(timestamp)')
        
        # Таблица артефактов
        conn.execute('''
            CREATE TABLE IF NOT EXISTS project_artifacts (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                artifact_type TEXT NOT NULL,
                name TEXT NOT NULL,
                filename TEXT NOT NULL,
                version TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_artifacts_project_id ON project_artifacts(project_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_artifacts_type ON project_artifacts(artifact_type)')
        
        conn.commit()
        logger.info("Database initialized")
    finally:
        conn.close()

def get_connection() -> sqlite3.Connection:
    """Возвращает соединение с базой данных."""
    # Инициализируем базу данных при первом соединении
    if not DB_PATH.exists():
        init_db()
    return sqlite3.connect(DB_PATH)

def project_exists(project_id: str) -> bool:
    """Проверяет, существует ли проект с указанным ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE id = ?", (project_id,))
        return cur.fetchone() is not None

def get_project_status(project_id: str) -> Optional[str]:
    """Возвращает статус проекта (active/archived) или None, если проект не найден."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT status FROM projects WHERE id = ?", (project_id,))
        row = cur.fetchone()
        return row[0] if row else None

def create_project(project_id: str, name: str, description: Optional[str], now: str) -> None:
    """Создаёт запись проекта в базе данных."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, name, description, "active", now, now)
        )
        conn.commit()

def update_project(project_id: str, name: Optional[str], description: Optional[str], updated_at: str) -> None:
    """Обновляет имя и описание проекта."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE projects SET name = COALESCE(?, name), description = COALESCE(?, description), updated_at = ? WHERE id = ?",
            (name, description, updated_at, project_id)
        )
        conn.commit()

def delete_project(project_id: str, updated_at: str) -> None:
    """Мягкое удаление проекта (устанавливает статус 'archived')."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE projects SET status = 'archived', updated_at = ? WHERE id = ?", (updated_at, project_id))
        conn.commit()

def get_active_projects(limit: int, offset: int) -> List[Tuple]:
    """Возвращает список активных проектов с пагинацией."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM projects WHERE status = 'active' ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return cur.fetchall()

def get_all_projects(limit: int, offset: int) -> List[Tuple]:
    """Возвращает список всех проектов (включая архивные) с пагинацией."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM projects ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return cur.fetchall()

def get_project_by_id(project_id: str) -> Optional[Tuple]:
    """Возвращает запись проекта по ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM projects WHERE id = ?",
            (project_id,)
        )
        return cur.fetchone()

def name_exists_active(name: str) -> bool:
    """Проверяет, существует ли активный проект с таким именем."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name = ? AND status = 'active'", (name,))
        return cur.fetchone() is not None

def name_exists_other_active(name: str, exclude_id: str) -> bool:
    """Проверяет, существует ли активный проект с таким именем, исключая указанный ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM projects WHERE name = ? AND status = 'active' AND id != ?", (name, exclude_id))
        return cur.fetchone() is not None

def insert_message(project_id: str, role: str, content: str, message_type: str, timestamp: str) -> int:
    """Вставляет сообщение в базу данных и возвращает его ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_messages (project_id, role, content, timestamp, message_type) VALUES (?, ?, ?, ?, ?)",
            (project_id, role, content, timestamp, message_type)
        )
        conn.commit()
        return cur.lastrowid

def get_project_messages(project_id: str, limit: int, offset: int, since: Optional[str] = None) -> List[Tuple]:
    """Возвращает список сообщений проекта с пагинацией и фильтрацией по дате."""
    with get_connection() as conn:
        cur = conn.cursor()
        query = "SELECT id, project_id, role, content, timestamp, message_type FROM project_messages WHERE project_id = ?"
        params = [project_id]
        if since:
            query += " AND timestamp >= ?"
            params.append(since)
        query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cur.execute(query, params)
        return cur.fetchall()

def insert_artifact(artifact_id: str, project_id: str, artifact_type: str, name: str, filename: str, version: Optional[str], created_at: str) -> None:
    """Вставляет запись артефакта в базу данных."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_artifacts (id, project_id, artifact_type, name, filename, version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (artifact_id, project_id, artifact_type, name, filename, version, created_at)
        )
        conn.commit()

def delete_artifact(artifact_id: str) -> None:
    """Удаляет запись артефакта из базы данных."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM project_artifacts WHERE id = ?", (artifact_id,))
        conn.commit()

def get_artifact_metadata(artifact_id: str) -> Optional[Tuple]:
    """Возвращает метаданные артефакта по ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, project_id, artifact_type, name, version, created_at FROM project_artifacts WHERE id = ?",
            (artifact_id,)
        )
        return cur.fetchone()

def get_artifact_filename(artifact_id: str) -> Optional[str]:
    """Возвращает имя файла артефакта по ID."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT filename FROM project_artifacts WHERE id = ?", (artifact_id,))
        row = cur.fetchone()
        return row[0] if row else None

def get_artifacts_by_project(project_id: str, artifact_type: Optional[str], limit: int, offset: int) -> List[Tuple]:
    """Возвращает список артефактов проекта с пагинацией и фильтрацией по типу."""
    with get_connection() as conn:
        cur = conn.cursor()
        if artifact_type:
            cur.execute(
                "SELECT id, project_id, artifact_type, name, version, created_at FROM project_artifacts WHERE project_id = ? AND artifact_type = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (project_id, artifact_type, limit, offset)
            )
        else:
            cur.execute(
                "SELECT id, project_id, artifact_type, name, version, created_at FROM project_artifacts WHERE project_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (project_id, limit, offset)
            )
        return cur.fetchall()

def get_artifact_file_path(project_id: str, artifact_id: str) -> Path:
    """Возвращает путь к файлу артефакта."""
    return PROJECTS_ROOT / project_id / "artifacts" / f"{artifact_id}.txt"

def recover_project_from_metadata(project_id: str, metadata: dict) -> None:
    """Восстанавливает проект из metadata.json."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO projects (id, name, description, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, metadata.get("name"), metadata.get("description"),
             metadata.get("status", "active"), metadata.get("created_at"), metadata.get("updated_at"))
        )
        conn.commit()

def recover_artifact(artifact_id: str, project_id: str, filename: str) -> None:
    """Восстанавливает артефакт из файловой системы."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO project_artifacts (id, project_id, artifact_type, name, filename, version, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (artifact_id, project_id, "unknown", f"Recovered {artifact_id}", filename, None, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()