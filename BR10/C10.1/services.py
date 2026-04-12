import logging
import subprocess
import re
import traceback
import json
from pathlib import Path
import repositories
import httpx
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

# Шаблоны для fallback-генерации (TODO-приложение)
MAIN_PY_TEMPLATE = """from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.orm import Session
from . import models, database

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

@app.get("/")
def root():
    return {"message": "TODO App"}

@app.get("/tasks")
def get_tasks(db: Session = Depends(database.get_db)):
    tasks = db.query(models.Task).all()
    return tasks

@app.post("/tasks")
def create_task(title: str, description: str = "", db: Session = Depends(database.get_db)):
    task = models.Task(title=title, description=description, status="pending")
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@app.put("/tasks/{task_id}")
def update_task(task_id: int, title: str = None, description: str = None, status: str = None, db: Session = Depends(database.get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if status is not None:
        task.status = status
    db.commit()
    db.refresh(task)
    return task

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(database.get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    return {"message": "Task deleted"}
"""

MODELS_PY_TEMPLATE = """from sqlalchemy import Column, Integer, String, Boolean
from .database import Base

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(String, default="")
    status = Column(String, default="pending")
"""

DATABASE_PY_TEMPLATE = """from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./todo.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

REQUIREMENTS_TXT = """fastapi
uvicorn
sqlalchemy
python-dotenv
"""

INDEX_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TODO App</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
        .task { border: 1px solid #ddd; padding: 10px; margin: 10px 0; border-radius: 5px; }
        .task.pending { background-color: #fff3cd; }
        .task.completed { background-color: #d4edda; }
        form { margin: 20px 0; }
        input, textarea, button { display: block; margin: 10px 0; padding: 10px; width: 100%; box-sizing: border-box; }
    </style>
</head>
<body>
    <h1>TODO App</h1>
    
    <form id="taskForm">
        <input type="text" id="title" placeholder="Task title" required>
        <textarea id="description" placeholder="Task description"></textarea>
        <button type="submit">Add Task</button>
    </form>
    
    <div id="tasks"></div>
    
    <script>
        async function loadTasks() {
            const response = await fetch('/tasks');
            const tasks = await response.json();
            const container = document.getElementById('tasks');
            container.innerHTML = '';
            tasks.forEach(task => {
                const div = document.createElement('div');
                div.className = `task ${task.status}`;
                div.innerHTML = `
                    <h3>${task.title}</h3>
                    <p>${task.description || ''}</p>
                    <p><strong>Status:</strong> ${task.status}</p>
                    <button onclick="updateTask(${task.id}, 'completed')">Mark Complete</button>
                    <button onclick="deleteTask(${task.id})">Delete</button>
                `;
                container.appendChild(div);
            });
        }
        
        async function addTask(title, description) {
            await fetch('/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ title, description })
            });
            loadTasks();
        }
        
        async function updateTask(id, status) {
            await fetch(`/tasks/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ status })
            });
            loadTasks();
        }
        
        async function deleteTask(id) {
            await fetch(`/tasks/${id}`, { method: 'DELETE' });
            loadTasks();
        }
        
        document.getElementById('taskForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const title = document.getElementById('title').value;
            const description = document.getElementById('description').value;
            await addTask(title, description);
            e.target.reset();
        });
        
        loadTasks();
    </script>
</body>
</html>
"""

REPO_PATH = Path("02_ПРОДУКТ/РЕПО")
PATCHES_DIR = Path("01_ЦЕХ/ЧЕРНОВИКИ/СПЕКИ")
BUILD_CONFIG = REPO_PATH / "build_config.json"

def _get_required_skills_from_patches(patch_ids: list[str]) -> list[str]:
    skills = []
    for pid in patch_ids:
        spec_file = PATCHES_DIR / f"{pid}.md"
        if not spec_file.exists():
            continue
        with open(spec_file, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"required_skills:\s*\[(.*?)\]", content)
        if match:
            for s in match.group(1).split(','):
                skills.append(s.strip().strip('"').strip("'"))
    return skills

def _apply_patches(patch_ids: list[str]) -> bool:
    for pid in patch_ids:
        spec_file = PATCHES_DIR / f"{pid}.md"
        if not spec_file.exists():
            logger.error(f"Patch spec not found: {spec_file}")
            return False
        with open(spec_file, "r", encoding="utf-8") as f:
            content = f.read()
        code_blocks = re.findall(r"```python\n(.*?)```", content, re.DOTALL)
        if not code_blocks:
            logger.warning(f"No code block found in {pid}")
            continue
        code = code_blocks[0]
        target_file = REPO_PATH / "bot.py"
        target_file.write_text(code, encoding="utf-8")
        logger.info(f"Applied patch {pid} to {target_file}")
    return True

def _run_build() -> bool:
    build_script = Path(__file__).parent / "build.py"
    if not build_script.exists():
        logger.info("build.py not found, skipping build")
        return True
    try:
        subprocess.run([str(build_script)], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Build failed: {e.stderr}")
        return False

async def fetch_patches_details(patch_ids: list) -> list:
    """
    Читает 01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json и извлекает для каждого patch_id
    его title, description, dependencies, required_skills.
    """
    queue_path = Path("01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json")
    if not queue_path.exists():
        logger.warning(f"Queue file not found: {queue_path}")
        return []
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        patches_by_id = {p["id"]: p for p in data.get("patches", [])}
        result = []
        for pid in patch_ids:
            if pid in patches_by_id:
                result.append(patches_by_id[pid])
            else:
                result.append({"id": pid, "title": "Unknown", "description": "No details"})
        logger.info(f"Fetched details for {len(result)} patches")
        return result
    except Exception as e:
        logger.error(f"Failed to fetch patches details: {e}")
        logger.error(traceback.format_exc())
        return []

def build_patches(task_id: str, patch_ids: list[str], check_skills: bool, run_tests: bool) -> tuple[bool, str]:
    try:
        logger.info(f"Starting build_patches for task {task_id}, patches: {patch_ids}")
        if check_skills:
            skills = _get_required_skills_from_patches(patch_ids)
            logger.info(f"Skills required for task {task_id}: {skills}")
        if not _apply_patches(patch_ids):
            logger.error(f"_apply_patches failed for patches: {patch_ids}")
            return False, "Failed to apply patches"
        if not _run_build():
            logger.error("_run_build failed")
            return False, "Build failed"
        if task_id:
            repositories.update_task_status(task_id, "ON_REVIEW", "Build completed")
        logger.info(f"build_patches completed successfully for task {task_id}")
        return True, "Build started"
    except Exception as e:
        logger.error(f"Build process error: {e}")
        logger.error(traceback.format_exc())
        return False, str(e)

async def generate_code_from_l5(container_id: str, spec: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Вызывает навык code_generation через C7.4.
    Возвращает список файлов [{"path": "...", "content": "..."}].
    В случае ошибки выбрасывает исключение.
    """
    url = "http://skill-integrator:8090/execute"
    payload = {
        "task_type": "code_generation",
        "context": {
            "container_id": container_id,
            "spec": spec
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = await resp.json()
            # Формат ответа C7.4: {"result": {...}, "skill_id": "...", "warnings": []}
            result_data = data.get("result", {})
            if "files" in result_data:
                return result_data["files"]
            else:
                error_msg = result_data.get("error", "Generation failed: no files in result")
                raise Exception(error_msg)
    except Exception as e:
        raise Exception(f"Failed to generate code: {str(e)}")

async def generate_code_from_patches(project_id: str, patch_ids: list) -> list:
    """
    Генерирует код для патчей (или для проекта) через навык code_generation.
    Временно: навык code_generation не работает, всегда используем fallback TODO-приложения.
    Возвращает список файлов [{"filename": "...", "content": "..."}].
    """
    logger.warning(f"Skill-based generation disabled due to 502, using universal fallback for TODO app (project_id={project_id}, patch_ids={patch_ids})")
    
    # Временно: навык code_generation не работает, всегда используем fallback TODO-приложения
    return [
        {"filename": "main.py", "content": MAIN_PY_TEMPLATE},
        {"filename": "models.py", "content": MODELS_PY_TEMPLATE},
        {"filename": "database.py", "content": DATABASE_PY_TEMPLATE},
        {"filename": "requirements.txt", "content": REQUIREMENTS_TXT},
        {"filename": "templates/index.html", "content": INDEX_HTML_TEMPLATE},
    ]

async def build_from_queue(queue: list) -> dict:
    """
    Принимает очередь патчей (список патчей с полями container_id, spec и т.д.).
    Для каждого патча вызывает generate_code_from_l5 и собирает результаты.
    """
    results = []
    for item in queue:
        container_id = item.get("container_id")
        spec = item.get("spec")
        if not container_id or not spec:
            results.append({"error": "Missing container_id or spec in queue item"})
            continue
        try:
            files = await generate_code_from_l5(container_id, spec)
            results.append({"container_id": container_id, "status": "success", "files": files})
        except Exception as e:
            results.append({"container_id": container_id, "status": "error", "error": str(e)})
    return {"total": len(queue), "results": results}
