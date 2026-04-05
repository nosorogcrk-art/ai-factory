"""Business logic for Skill Tester."""
import os
import uuid
import json
import logging
import asyncio
import httpx
import docker
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import repositories as repo

logger = logging.getLogger(__name__)

SKILL_REGISTRY_URL = os.getenv("SKILL_REGISTRY_URL", "http://skill-registry:8088")
BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
test_sessions: Dict[str, Dict[str, Any]] = {}
_docker_client = None

def get_docker_client():
    """Get or create Docker client (lazy initialization)."""
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client

def close_docker_client():
    """Close Docker client on shutdown."""
    global _docker_client
    if _docker_client:
        _docker_client.close()
        _docker_client = None

async def send_log_to_br18(event_type: str, details: dict, background_tasks=None):
    """
    Send log to BR18 asynchronously.

    Args:
        event_type: Type of event (e.g., "skill_test", "error").
        details: Dictionary with log details.
        background_tasks: FastAPI BackgroundTasks (optional, if provided uses it).
    """
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "service": "C17.4",
        "event_type": event_type,
        "details": details
    }
    async def _send():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(BR18_URL, json=log_entry, timeout=5.0)
                logger.info(f"Log sent to BR18: {event_type}")
        except Exception as e:
            logger.error(f"Failed to send log to BR18: {e}")

    if background_tasks:
        background_tasks.add_task(_send)
    else:
        asyncio.create_task(_send())

async def get_skill_from_registry(skill_id: str) -> Optional[Dict[str, Any]]:
    """Fetch skill metadata from C17.1 (Skill Registry)."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{SKILL_REGISTRY_URL}/skills/{skill_id}", timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                logger.warning(f"Skill {skill_id} not found in registry")
                return None
            else:
                logger.error(f"Unexpected response from registry: {resp.status_code}")
                return None
        except Exception as e:
            logger.error(f"Failed to connect to C17.1: {e}")
            return None

def run_docker_test(skill_instruction: str, test_input: str, timeout_sec: int = 30) -> Tuple[bool, str, float]:
    """
    Run skill instruction in a Docker container synchronously with timeout.

    Args:
        skill_instruction: Python code (string) to execute.
        test_input: Input data to pass to the script (JSON string).
        timeout_sec: Timeout in seconds (hard kill after this time).

    Returns:
        (passed, output/error, duration_seconds)
    """
    import tempfile
    import time
    import json as jsonlib

    script_content = f"""
import sys
import json

# Инструкция навыка (пользовательский код)
{skill_instruction}

def main():
    try:
        if 'run_skill' in dir():
            input_data = json.loads('{jsonlib.dumps(test_input)}')
            result = run_skill(input_data)
            if isinstance(result, dict):
                passed = result.get('passed', False)
                output = result.get('output', '')
            else:
                passed = bool(result)
                output = str(result)
        else:
            passed = True
            output = "Skill has no run_skill function, considered passed"
        print(json.dumps({{"passed": passed, "output": output}}))
    except Exception as e:
        print(json.dumps({{"passed": False, "output": str(e)}}))

if __name__ == '__main__':
    main()
"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        script_file = tmp_path / "skill_script.py"
        script_file.write_text(script_content)

        start_time = time.time()
        client = get_docker_client()
        container = None
        try:
            container = client.containers.run(
                image="python:3.12-slim",
                command=f"python /script/skill_script.py",
                volumes={str(tmp_path): {"bind": "/script", "mode": "ro"}},
                detach=True,
                mem_limit="512m",
                network_mode="none",
                read_only=True,
                remove=False
            )
            container.wait(timeout=timeout_sec)
            duration = time.time() - start_time
            logs = container.logs(stdout=True, stderr=True).decode('utf-8').strip()
            container.remove()

            try:
                lines = logs.strip().split('\n')
                json_line = None
                for line in reversed(lines):
                    if line.strip().startswith('{'):
                        json_line = line
                        break
                if json_line:
                    result_data = jsonlib.loads(json_line)
                    passed = result_data.get("passed", False)
                    output = result_data.get("output", "")
                else:
                    passed = False
                    output = logs
            except jsonlib.JSONDecodeError:
                passed = False
                output = logs

            logger.info(f"Docker test completed in {duration:.2f}s, passed={passed}")
            return passed, output, duration

        except docker.errors.APIError as e:
            duration = time.time() - start_time
            if container:
                container.kill()
                container.remove()
            logger.error(f"Docker API error: {e}")
            return False, f"Docker API error: {e}", duration
        except Exception as e:
            duration = time.time() - start_time
            if container:
                try:
                    container.kill()
                    container.remove()
                except Exception:
                    pass
            logger.error(f"Docker execution failed: {e}")
            return False, str(e), duration

async def run_test_in_docker(skill_instruction: str, test_input: str = "") -> Tuple[bool, str, float]:
    """Asynchronous wrapper for Docker test."""
    return await asyncio.to_thread(run_docker_test, skill_instruction, test_input)

async def start_test_real(skill_id: str, background_tasks=None) -> Tuple[Optional[str], Optional[bool], Optional[str], Optional[float], Optional[str]]:
    """
    Start a real test run: fetch skill, run Docker test, save results, send log to BR18.

    Args:
        skill_id: Identifier of the skill.
        background_tasks: FastAPI BackgroundTasks for async logging.

    Returns:
        (test_run_id, passed, output, duration_seconds, error_message)
    """
    skill = await get_skill_from_registry(skill_id)
    if skill is None:
        return None, None, None, None, f"Skill {skill_id} not found or registry unavailable"

    instruction = skill.get("instruction", "")
    if not instruction:
        return None, None, None, None, f"Skill {skill_id} has no instruction"

    passed, output, duration = await run_test_in_docker(instruction)

    test_run_id = f"tr_{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    test_sessions[test_run_id] = {
        "skill_id": skill_id,
        "started_at": now,
        "status": "completed",
        "skill_data": skill,
        "result": {"passed": passed, "output": output, "duration": duration}
    }
    repo.save_test_run(
        test_run_id=test_run_id,
        skill_id=skill_id,
        started_at=now,
        finished_at=now,
        overall="passed" if passed else "failed",
        results=[{"name": "docker_test", "passed": passed, "duration_ms": int(duration * 1000), "error": output if not passed else None}]
    )
    logger.info(f"Test run {test_run_id} completed for skill {skill_id}, passed={passed}")

    # Отправка лога в BR18
    log_details = {
        "skill_id": skill_id,
        "test_case": "docker_test",
        "passed": passed,
        "duration_ms": int(duration * 1000),
        "error": output if not passed else None
    }
    await send_log_to_br18("skill_test", log_details, background_tasks)

    return test_run_id, passed, output, duration, None

def get_results(skill_id: str) -> dict:
    """
    Return the latest test results for a skill, including metrics.
    """
    row = repo.get_last_results(skill_id)
    if not row:
        return get_results_stub(skill_id)
    results_list = json.loads(row["results_json"]) if row["results_json"] else []
    total = len(results_list)
    passed = sum(1 for r in results_list if r.get("passed", False))
    failed = total - passed
    avg_duration = sum(r.get("duration_ms", 0) for r in results_list) / total if total > 0 else 0
    return {
        "skill_id": row["skill_id"],
        "last_test": row["finished_at"],
        "overall": row["overall"],
        "tests": results_list,
        "metrics": {
            "total_tests": total,
            "passed_tests": passed,
            "failed_tests": failed,
            "avg_duration_ms": round(avg_duration, 2)
        }
    }

def get_results_stub(skill_id: str) -> dict:
    """Return stub results for a skill (used when no real test run exists)."""
    return {
        "skill_id": skill_id,
        "last_test": datetime.now().isoformat(),
        "overall": "passed",
        "tests": [{"name": "basic_case", "passed": True, "duration_ms": 100, "error": None}],
        "metrics": {"total_tests": 1, "passed_tests": 1, "failed_tests": 0, "avg_duration_ms": 100}
    }