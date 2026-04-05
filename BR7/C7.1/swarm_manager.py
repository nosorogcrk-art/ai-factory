#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
swarm_manager.py – менеджер роя микро-агентов с вызовом Skill Integrator.
Передаёт полученный промпт агенту через временный файл.
"""

import json
import subprocess
import threading
import time
import logging
import sys
import os
import asyncio
import httpx
import tempfile
from pathlib import Path
from queue import Queue
from datetime import datetime

TEMPLATES_DIR = Path("00_КАНОН/Шаблоны/Специалисты")
REQUESTS_DIR = Path("01_ЦЕХ/01_ЖУРНАЛЫ/ЗАПРОСЫ_СПЕЦИАЛИСТОВ")
RESPONSES_DIR = Path("01_ЦЕХ/01_ЖУРНАЛЫ/ОТВЕТЫ_СПЕЦИАЛИСТОВ")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/swarm_manager.log")
MAX_CONCURRENT = 5
SKILL_INTEGRATOR_URL = os.getenv("SKILL_INTEGRATOR_URL", "http://localhost:8091")

REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

request_queue = Queue()
active_requests = 0
queue_lock = threading.Lock()

def load_template(template_name):
    path = TEMPLATES_DIR / f"{template_name}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

async def fetch_prompt_from_integrator(task_type, language=None, context=None, required_skills=None, agent_type="main"):
    """Запрашивает промпт у Skill Integrator."""
    async with httpx.AsyncClient() as client:
        payload = {
            "task_type": task_type,
            "agent_type": agent_type,
            "language": language,
            "context": context,
            "required_skills": required_skills,
            "limit": 5
        }
        try:
            resp = await client.post(f"{SKILL_INTEGRATOR_URL}/compile", json=payload, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            return data["prompt"], data["used_skills"], data.get("warnings", [])
        except Exception as e:
            logging.error(f"Failed to call skill integrator: {e}")
            return None, [], [str(e)]

def spawn_agent(request):
    req_id = request["request_id"]
    template_name = request.get("template_name")
    task_type = request.get("task_type", "generic")
    language = request.get("language")
    context = request.get("context", {})
    reply_to = request.get("reply_to", str(RESPONSES_DIR))
    required_skills = request.get("required_skills")
    agent_type = request.get("agent_type", "main")
    budget = request.get("budget", 10)

    # Получаем промпт от интегратора
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        prompt, used_skills, warnings = loop.run_until_complete(
            fetch_prompt_from_integrator(task_type, language, json.dumps(context), required_skills, agent_type)
        )
    finally:
        loop.close()

    if prompt is None:
        # fallback: используем шаблон
        template = load_template(template_name) if template_name else None
        if template:
            prompt = template.get("prompt", "")
            for key, value in context.items():
                prompt = prompt.replace("{{" + key + "}}", str(value))
        else:
            prompt = f"[FALLBACK] No prompt available for task {req_id}"

    # Создаём временный файл с промптом
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        prompt_file = f.name
        f.write(prompt)

    # Скрипт микро-агента, читающий промпт из файла
    agent_script = f'''#!/usr/bin/env python3
import sys, json, os
result_file = sys.argv[1]
prompt_file = sys.argv[2]
with open(prompt_file, 'r', encoding='utf-8') as f:
    prompt = f.read()
result = {{
    "request_id": "{req_id}",
    "prompt_preview": prompt[:200],
    "budget": {budget}
}}
with open(result_file, "w", encoding="utf-8") as f:
    json.dump(result, f)
os.unlink(prompt_file)
'''
    script_path = Path(f"/tmp/agent_{req_id}.py")
    script_path.write_text(agent_script, encoding="utf-8")
    os.chmod(script_path, 0o755)

    result_file = Path(reply_to) / f"response_{req_id}.json"
    try:
        subprocess.run([sys.executable, str(script_path), str(result_file), prompt_file],
                       timeout=60, check=True)
        logging.info(f"Request {req_id} completed successfully.")
    except subprocess.TimeoutExpired:
        logging.error(f"Request {req_id} timed out.")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({"error": "timeout", "request_id": req_id}, f)
    except Exception as e:
        logging.error(f"Request {req_id} failed: {e}")
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump({"error": str(e), "request_id": req_id}, f)
    finally:
        script_path.unlink(missing_ok=True)
        try:
            os.unlink(prompt_file)
        except:
            pass

def worker():
    while True:
        request = request_queue.get()
        if request is None:
            break
        with queue_lock:
            global active_requests
            active_requests += 1
        try:
            spawn_agent(request)
        finally:
            with queue_lock:
                active_requests -= 1
        request_queue.task_done()

def start_workers(n):
    for _ in range(n):
        t = threading.Thread(target=worker, daemon=True)
        t.start()

start_workers(MAX_CONCURRENT)

def scan_requests():
    for file in REQUESTS_DIR.glob("*.json"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                request = json.load(f)
            if "request_id" in request:
                request_queue.put(request)
                logging.info(f"Queued request {request['request_id']}")
                file.unlink()
            else:
                logging.warning(f"Invalid request file {file.name}")
        except Exception as e:
            logging.error(f"Error processing {file.name}: {e}")

def main():
    logging.info(f"Swarm manager started with {MAX_CONCURRENT} workers.")
    while True:
        scan_requests()
        time.sleep(5)

if __name__ == "__main__":
    main()
