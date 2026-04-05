import os
import httpx
import logging
from typing import Optional, Dict, Any, List
import repositories as cache_repo

logger = logging.getLogger(__name__)

SKILL_REGISTRY_URL = os.getenv("SKILL_REGISTRY_URL", "http://skill-registry:8088")
SKILL_VERSION_CONTROL_URL = os.getenv("SKILL_VERSION_CONTROL_URL", "http://skill-version-control:8089")
SKILL_TESTER_URL = os.getenv("SKILL_TESTER_URL", "http://skill-tester:8091")
ENABLE_SKILL_TEST_CHECK = os.getenv("ENABLE_SKILL_TEST_CHECK", "false").lower() == "true"

async def fetch_skill_from_registry(skill_id: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{SKILL_REGISTRY_URL}/skills/{skill_id}")
            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 404:
                return None
            else:
                logger.error(f"Registry error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch from registry: {e}")
            return None

async def fetch_skill_from_version_control(skill_id: str, version: str) -> Optional[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{SKILL_VERSION_CONTROL_URL}/file/{skill_id}", params={"ref": version})
            if resp.status_code == 200:
                return resp.json()
            else:
                logger.error(f"Version control error {resp.status_code}: {resp.text}")
                return None
        except Exception as e:
            logger.error(f"Failed to fetch from version control: {e}")
            return None

async def check_skill_test_status(skill_id: str) -> bool:
    if not ENABLE_SKILL_TEST_CHECK:
        return True
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"{SKILL_TESTER_URL}/results/{skill_id}")
            if resp.status_code == 200:
                data = resp.json()
                return data.get("overall") == "passed"
            else:
                logger.warning(f"Skill test check failed with {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to check test status: {e}")
            return False

def build_skill_response(skill_data: dict) -> dict:
    return {
        "id": skill_data["id"],
        "version": skill_data["version"],
        "name": skill_data["name"],
        "instruction": skill_data["instruction"],
        "dependencies": skill_data.get("depends_on", []),
        "metadata": {
            "tags": skill_data.get("tags", []),
            "task_types": skill_data.get("task_types", []),
            "languages": skill_data.get("languages", []),
            "allowed_for_swarm": skill_data.get("allowed_for_swarm", False),
            "status": skill_data.get("status"),
            "author": skill_data.get("author"),
            "description": skill_data.get("description"),
            "created_at": skill_data.get("created_at"),
            "updated_at": skill_data.get("updated_at")
        }
    }

async def get_skill(skill_id: str, version: Optional[str] = None, agent_type: str = "main") -> Optional[dict]:
    cache_key = f"{skill_id}:{version or 'latest'}:{agent_type}"
    cached = cache_repo.get_from_cache(cache_key)
    if cached:
        logger.info(f"Cache hit for {cache_key}")
        return cached

    if version:
        skill_data = await fetch_skill_from_version_control(skill_id, version)
    else:
        skill_data = await fetch_skill_from_registry(skill_id)
    if not skill_data:
        return None

    if agent_type == "swarm" and not skill_data.get("allowed_for_swarm", False):
        logger.warning(f"Skill {skill_id} not allowed for swarm")
        return None

    if not await check_skill_test_status(skill_id):
        logger.warning(f"Skill {skill_id} did not pass tests")
        return None

    response = build_skill_response(skill_data)
    cache_repo.set_in_cache(cache_key, response)
    return response