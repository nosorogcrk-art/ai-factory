"""Бизнес-логика Test Stand."""
import os
import asyncio
import logging
import subprocess
import shlex
import shutil
import tempfile
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import httpx

import repositories as repo

logger = logging.getLogger(__name__)

PRODUCT_PATH = os.getenv("PRODUCT_PATH", "/app/02_ПРОДУКТ/РЕПО")
TEST_SUITE = os.getenv("TEST_SUITE", "tests")
DEFAULT_IMAGE = os.getenv("DEFAULT_IMAGE", "python:3.12-slim")
LOG_DIR = Path(os.getenv("LOG_DIR", "/app/logs"))
RESULTS_DIR = LOG_DIR / "test_results"
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"
SKILL_TESTER_URL = os.getenv("SKILL_TESTER_URL", "http://skill-tester:8091")
HOST_TEMP_DIR = Path(tempfile.gettempdir())

LOG_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

_running_processes: Dict[str, asyncio.subprocess.Process] = {}

async def send_to_br18(event_type: str, details: dict):
    """Отправляет событие в BR18 (асинхронно)."""
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now().isoformat(),
                    "service": "C10.2",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

def check_docker_socket():
    """Проверяет доступность Docker сокета."""
    try:
        subprocess.run(["docker", "ps"], capture_output=True, check=True)
        logger.info("Docker socket is accessible.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker socket check failed: {e.stderr}")
        raise RuntimeError("Cannot access Docker socket")
    except FileNotFoundError:
        logger.error("Docker executable not found")
        raise RuntimeError("Docker executable not found")

async def check_skills_real(skills: List[str], job_id: str) -> Tuple[bool, List[dict]]:
    """
    Проверяет навыки через C17.4 (Skill Tester).

    Args:
        skills: Список ID навыков.
        job_id: ID задания (для логирования).

    Returns:
        (все_навыки_пройдены, детали_результатов)
    """
    if not skills:
        return True, []
    results = []
    all_passed = True
    async with httpx.AsyncClient(timeout=30.0) as client:
        for skill_id in skills:
            try:
                resp = await client.post(f"{SKILL_TESTER_URL}/test/{skill_id}")
                if resp.status_code == 200:
                    data = resp.json()
                    passed = data.get("passed", False)
                    output = data.get("output", "")
                    duration = data.get("duration_seconds", 0)
                else:
                    passed = False
                    output = f"HTTP {resp.status_code}: {resp.text}"
                    duration = 0
            except Exception as e:
                passed = False
                output = str(e)
                duration = 0
            results.append({
                "skill_id": skill_id,
                "passed": passed,
                "output": output,
                "duration_seconds": duration
            })
            if not passed:
                all_passed = False
            logger.info(f"Skill {skill_id} test passed={passed}")
            await send_to_br18("skill_test", {
                "job_id": job_id,
                "skill_id": skill_id,
                "passed": passed,
                "output": output[:200]
            })
    return all_passed, results

async def run_tests_async(job_id: str, request):
    """
    Выполняет тесты в Docker-контейнере, предварительно проверяя навыки.

    Args:
        job_id: Идентификатор задания.
        request: Объект TestRequest с параметрами.
    """
    job = repo.load_job(job_id)
    if not job:
        return
    job["status"] = "running"
    job["started_at"] = datetime.now().isoformat()
    repo.save_job(job)

    product_path = Path(request.product_path)
    if not product_path.exists():
        job["status"] = "failed"
        job["finished_at"] = datetime.now().isoformat()
        job["error"] = f"Product path not found: {product_path}"
        repo.save_job(job)
        await send_to_br18("test_failed", {"job_id": job_id, "error": job["error"]})
        return

    # Загрузка метаданных навыков
    metadata_path = product_path / "metadata.json"
    skills = []
    if metadata_path.exists():
        try:
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                skills = metadata.get("skills", [])
        except Exception as e:
            logger.warning(f"Failed to load metadata.json: {e}")
    logger.info(f"Skills to check: {skills}")

    # Проверка навыков через C17.4
    skills_passed, skill_results = await check_skills_real(skills, job_id)
    if not skills_passed:
        job["status"] = "failed"
        job["finished_at"] = datetime.now().isoformat()
        job["error"] = f"Skill tests failed: {skill_results}"
        repo.save_job(job)
        await send_to_br18("test_failed", {"job_id": job_id, "error": job["error"]})
        return

    host_tmp_dir = HOST_TEMP_DIR / f"test_stand_{job_id}"
    host_tmp_dir.mkdir(parents=True, exist_ok=True)

    try:
        report_file = host_tmp_dir / "report.json"

        safe_suite = shlex.quote(request.test_suite)
        test_cmd = f"""
set -e
pip install --quiet --root-user-action=ignore pytest pytest-json-report
cd /product && pytest {safe_suite} --json-report --json-report-file=/results/report.json
"""
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{product_path}:/product",
            "-v", f"{host_tmp_dir}:/results",
            request.image,
            "sh", "-c", test_cmd
        ]

        logger.info(f"Running job {job_id}: {' '.join(cmd)}")
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _running_processes[job_id] = proc
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=request.timeout_seconds
            )
            if stdout:
                logger.info(f"Job {job_id} stdout: {stdout.decode()}")
            if stderr:
                logger.info(f"Job {job_id} stderr: {stderr.decode()}")
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            job["status"] = "timeout"
            job["error"] = f"Job timed out after {request.timeout_seconds} seconds."
            logger.error(job["error"])
        else:
            if proc.returncode == 0:
                job["status"] = "completed"
                logger.info(f"Job {job_id} completed successfully.")
            elif proc.returncode == 5:
                job["status"] = "completed"
                job["error"] = "No tests found"
                logger.warning(f"Job {job_id}: no tests found.")
            else:
                job["status"] = "failed"
                job["error"] = f"Tests failed with code {proc.returncode}: {stderr.decode()}"
                logger.error(job["error"])
        finally:
            _running_processes.pop(job_id, None)
            job["finished_at"] = datetime.now().isoformat()

        if report_file.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest_file = RESULTS_DIR / f"test_result_{timestamp}_{job_id}.json"
            shutil.copy2(report_file, dest_file)
            job["report_file"] = str(dest_file)
            logger.info(f"Test report saved to {dest_file}")
        else:
            if not job.get("error"):
                job["error"] = "No test report generated."
            logger.warning(f"Report file not found at {report_file}")

        repo.save_job(job)

        await send_to_br18(
            "test_completed",
            {
                "job_id": job_id,
                "status": job["status"],
                "report_file": job.get("report_file"),
                "error": job.get("error")
            }
        )
    finally:
        shutil.rmtree(host_tmp_dir, ignore_errors=True)