import os
import uuid
import subprocess
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import git
import httpx
import repositories as repo

logger = logging.getLogger(__name__)

BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

async def send_log_to_br18(event_type: str, details: dict) -> None:
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "service": "C20.1",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
            logger.info(f"Log sent to BR18: {event_type}")
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")

def clone_or_pull_repo(repo_url: str, branch: str, target_dir: Path) -> bool:
    try:
        if target_dir.exists():
            repo_obj = git.Repo(target_dir)
            repo_obj.git.checkout(branch)
            repo_obj.git.pull()
        else:
            git.Repo.clone_from(repo_url, target_dir, branch=branch)
        return True
    except Exception as e:
        logger.error(f"Git operation failed: {e}")
        return False

def run_docker_compose(compose_file: Path) -> bool:
    try:
        result = subprocess.run(
            ["docker-compose", "-f", str(compose_file), "up", "-d"],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Docker-compose output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Docker-compose failed: {e.stderr}")
        return False

async def perform_deployment(deployment_id: str, repo_url: str, branch: str, version: Optional[str] = None):
    logger.info(f"Deployment {deployment_id} started")
    await send_log_to_br18("deployment_started", {"deployment_id": deployment_id, "repo_url": repo_url, "branch": branch})

    deployment = repo.get_deployment(deployment_id)
    if deployment is None:
        logger.error(f"Deployment {deployment_id} not found")
        await send_log_to_br18("deployment_failed", {"deployment_id": deployment_id, "error": "Deployment not found"})
        return

    deployment["status"] = "running"
    repo.save_deployment(deployment)

    repo_path = Path(f"/tmp/gitops_repo/{deployment_id}")
    compose_file = repo_path / "docker-compose.yml"

    success = clone_or_pull_repo(repo_url, branch, repo_path)
    if not success:
        deployment["status"] = "failed"
        deployment["finished_at"] = datetime.now(timezone.utc).isoformat()
        deployment["log"] = "Failed to clone/pull repository"
        repo.save_deployment(deployment)
        await send_log_to_br18("deployment_failed", {"deployment_id": deployment_id, "error": deployment["log"]})
        return

    if not compose_file.exists():
        deployment["status"] = "failed"
        deployment["finished_at"] = datetime.now(timezone.utc).isoformat()
        deployment["log"] = "docker-compose.yml not found in repository"
        repo.save_deployment(deployment)
        await send_log_to_br18("deployment_failed", {"deployment_id": deployment_id, "error": deployment["log"]})
        return

    if not run_docker_compose(compose_file):
        deployment["status"] = "failed"
        deployment["finished_at"] = datetime.now(timezone.utc).isoformat()
        deployment["log"] = "Docker-compose up failed"
        repo.save_deployment(deployment)
        await send_log_to_br18("deployment_failed", {"deployment_id": deployment_id, "error": deployment["log"]})
        return

    deployment["status"] = "completed"
    deployment["finished_at"] = datetime.now(timezone.utc).isoformat()
    deployment["log"] = "Deployment successful"
    repo.save_deployment(deployment)
    await send_log_to_br18("deployment_completed", {"deployment_id": deployment_id})
    logger.info(f"Deployment {deployment_id} completed successfully")