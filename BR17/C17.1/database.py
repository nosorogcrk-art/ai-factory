import sqlite3
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Dict

DB_PATH = Path("/data/skills.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            description TEXT NOT NULL,
            author TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            tags TEXT NOT NULL DEFAULT '[]',
            task_types TEXT NOT NULL DEFAULT '[]',
            languages TEXT NOT NULL DEFAULT '[]',
            allowed_for_swarm INTEGER NOT NULL DEFAULT 0,
            depends_on TEXT NOT NULL DEFAULT '[]',
            related_patches TEXT NOT NULL DEFAULT '[]',
            instruction TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            soft_deleted INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON skills(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_name ON skills(name)')
    conn.commit()
    conn.close()

def _dict_to_row(skill: dict) -> tuple:
    return (
        skill['id'],
        skill['name'],
        skill['version'],
        skill['description'],
        skill['author'],
        skill['status'],
        json.dumps(skill.get('tags', [])),
        json.dumps(skill.get('task_types', [])),
        json.dumps(skill.get('languages', [])),
        1 if skill.get('allowed_for_swarm', False) else 0,
        json.dumps(skill.get('depends_on', [])),
        json.dumps(skill.get('related_patches', [])),
        skill['instruction'],
        skill['created_at'],
        skill['updated_at'],
        1 if skill.get('soft_deleted', False) else 0
    )

def _row_to_dict(row) -> dict:
    return {
        'id': row[0],
        'name': row[1],
        'version': row[2],
        'description': row[3],
        'author': row[4],
        'status': row[5],
        'tags': json.loads(row[6]),
        'task_types': json.loads(row[7]),
        'languages': json.loads(row[8]),
        'allowed_for_swarm': bool(row[9]),
        'depends_on': json.loads(row[10]),
        'related_patches': json.loads(row[11]),
        'instruction': row[12],
        'created_at': row[13],
        'updated_at': row[14],
        'soft_deleted': bool(row[15])
    }

def create_skill(skill: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO skills (
            id, name, version, description, author, status,
            tags, task_types, languages, allowed_for_swarm,
            depends_on, related_patches, instruction,
            created_at, updated_at, soft_deleted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', _dict_to_row(skill))
    conn.commit()
    conn.close()

def get_skill(skill_id: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM skills WHERE id = ?', (skill_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return _row_to_dict(row)
    return None

def get_all_skills(include_deleted: bool = False, filters: dict = None, limit: int = 20, offset: int = 0) -> List[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = 'SELECT * FROM skills WHERE 1=1'
    params = []
    if not include_deleted:
        query += ' AND soft_deleted = 0'
    if filters:
        if 'status' in filters:
            query += ' AND status = ?'
            params.append(filters['status'])
        if 'tags' in filters:
            query += ' AND tags LIKE ?'
            params.append(f'%{filters["tags"][0]}%')
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [_row_to_dict(row) for row in rows]

def count_skills(include_deleted: bool = False, filters: dict = None) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    query = 'SELECT COUNT(*) FROM skills WHERE 1=1'
    params = []
    if not include_deleted:
        query += ' AND soft_deleted = 0'
    if filters:
        if 'status' in filters:
            query += ' AND status = ?'
            params.append(filters['status'])
        if 'tags' in filters:
            query += ' AND tags LIKE ?'
            params.append(f'%{filters["tags"][0]}%')
    cursor.execute(query, params)
    count = cursor.fetchone()[0]
    conn.close()
    return count

def update_skill(skill_id: str, updated_data: dict) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM skills WHERE id = ?', (skill_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Skill {skill_id} not found")
    current = _row_to_dict(row)
    for key, value in updated_data.items():
        if key in ['tags', 'task_types', 'languages', 'depends_on', 'related_patches'] and value is not None:
            current[key] = value
        elif value is not None:
            current[key] = value
    current['updated_at'] = datetime.now(timezone.utc).isoformat()
    # Формируем кортеж из 15 значений (все поля кроме id)
    update_tuple = (
        current['name'], current['version'], current['description'],
        current['author'], current['status'], json.dumps(current['tags']),
        json.dumps(current['task_types']), json.dumps(current['languages']),
        1 if current['allowed_for_swarm'] else 0,
        json.dumps(current['depends_on']), json.dumps(current['related_patches']),
        current['instruction'], current['updated_at'],
        1 if current['soft_deleted'] else 0,
        skill_id  # для WHERE
    )
    cursor.execute('''
        UPDATE skills SET
            name=?, version=?, description=?, author=?, status=?,
            tags=?, task_types=?, languages=?, allowed_for_swarm=?,
            depends_on=?, related_patches=?, instruction=?,
            updated_at=?, soft_deleted=?
        WHERE id=?
    ''', update_tuple)
    conn.commit()
    conn.close()

def delete_skill(skill_id: str, hard: bool = False) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if hard:
        cursor.execute('DELETE FROM skills WHERE id = ?', (skill_id,))
    else:
        cursor.execute('UPDATE skills SET soft_deleted = 1, status = "deleted" WHERE id = ?', (skill_id,))
    conn.commit()
    conn.close()

def get_stats() -> dict:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    total = cursor.execute('SELECT COUNT(*) FROM skills').fetchone()[0]
    active = cursor.execute('SELECT COUNT(*) FROM skills WHERE status = "active" AND soft_deleted = 0').fetchone()[0]
    draft = cursor.execute('SELECT COUNT(*) FROM skills WHERE status = "draft" AND soft_deleted = 0').fetchone()[0]
    deprecated = cursor.execute('SELECT COUNT(*) FROM skills WHERE status = "deprecated" AND soft_deleted = 0').fetchone()[0]
    deleted = cursor.execute('SELECT COUNT(*) FROM skills WHERE soft_deleted = 1').fetchone()[0]
    conn.close()
    return {
        'total': total,
        'active': active,
        'draft': draft,
        'deprecated': deprecated,
        'deleted': deleted
    }