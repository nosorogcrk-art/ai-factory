import asyncio
import aiohttp
import json
import logging
import os

PROJECT_MEMORY_URL = os.getenv("PROJECT_MEMORY_URL", "http://project-memory:8090")
HANDOVER_URL = os.getenv("HANDOVER_URL", "http://handover:8080")
DIALOGUE_MANAGER_URL = os.getenv("DIALOGUE_MANAGER_URL", "http://dialogue-manager:8099")
COGNITIVE_ENGINE_URL = os.getenv("COGNITIVE_ENGINE_URL", "http://cognitive-engine:8103")
PROCESSED_FILE = "01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/processed_projects.json"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("argus_watcher")

async def get_projects():
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{PROJECT_MEMORY_URL}/projects") as resp:
            if resp.status == 200:
                return await resp.json()
            return []

async def create_task(project_id, project_name):
    task_id = f"PROJ-{project_id}"
    payload = {
        "task_id": task_id,
        "actor": "АРГУС",
        "comment": f"Автоматическая задача: новый проект '{project_name}' (ID: {project_id})"
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(f"{HANDOVER_URL}/take", json=payload) as resp:
            if resp.status == 200:
                logger.info(f"Task created for project {project_id}: {task_id}")
            else:
                logger.error(f"Failed to create task for project {project_id}: {resp.status}")

def load_processed():
    if not os.path.exists(PROCESSED_FILE):
        return set()
    with open(PROCESSED_FILE, "r") as f:
        return set(json.load(f))

def save_processed(processed):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)

async def start_dialogue(project_id: str, project_name: str):
    """Запускает диалог в C9.4 для нового проекта."""
    c94_url = f"{DIALOGUE_MANAGER_URL}/api/dialog"
    payload = {
        "project_id": project_id,
        "message": f"Начинаем опрос для нового проекта «{project_name}». Пожалуйста, опишите задачу."
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(c94_url, json=payload, timeout=10.0) as resp:
                if resp.status == 200:
                    logger.info(f"Dialogue started for project {project_id}")
                else:
                    logger.error(f"Failed to start dialogue for project {project_id}: HTTP {resp.status}")
    except Exception as e:
        logger.error(f"Error starting dialogue for project {project_id}: {e}")
    
    # Вызов C1.1 для генерации подсказок
    try:
        async with aiohttp.ClientSession() as session:
            await session.post(
                f"{COGNITIVE_ENGINE_URL}/generate_hints",
                json={"project_id": project_id, "initial_message": f"Новый проект {project_name}"},
                timeout=10.0
            )
        logger.info(f"Hints generation requested for project {project_id}")
    except Exception as e:
        logger.warning(f"Failed to generate hints for {project_id}: {e}")

async def watch_projects():
    logger.info("Argus watcher started")
    processed = load_processed()
    while True:
        try:
            projects = await get_projects()
            for project in projects:
                pid = project["id"]
                if pid not in processed:
                    logger.info(f"New project detected: {pid} - {project['name']}")
                    await create_task(pid, project["name"])
                    await start_dialogue(pid, project["name"])
                    processed.add(pid)
                    save_processed(processed)
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Watcher error: {e}")
            await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(watch_projects())
