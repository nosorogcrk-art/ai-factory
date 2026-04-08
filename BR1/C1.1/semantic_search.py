import json
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

PROJECT_MEMORY_URL = "http://project-memory:8108"
SEARCH_ENDPOINT = f"{PROJECT_MEMORY_URL}/search"
HINTS_DIR = Path("01_ЦЕХ/ПОДСКАЗКИ")

async def find_similar_projects(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Ищет похожие проекты в C2.6 по текстовому запросу."""
    if not query:
        return []
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                SEARCH_ENDPOINT,
                json={"query": query, "limit": limit},
                timeout=10.0
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
    except Exception as e:
        logger.error(f"Failed to search similar projects: {e}")
        return []

async def extract_hints_from_project(project_id: str) -> Dict[str, Any]:
    """Извлекает из проекта L2, патчи и спецификации."""
    hints = {"project_id": project_id, "l2": None, "patches": [], "specs": []}
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{PROJECT_MEMORY_URL}/projects/{project_id}/artifacts")
            resp.raise_for_status()
            artifacts = resp.json()
            for art in artifacts:
                art_type = art.get("artifact_type")
                if art_type in ("specification", "l2") and hints["l2"] is None:
                    hints["l2"] = art
                elif art_type == "patch":
                    hints["patches"].append(art)
                elif art_type == "specification" and art.get("name") != "L2_specification":
                    hints["specs"].append(art)
    except Exception as e:
        logger.error(f"Failed to fetch artifacts for project {project_id}: {e}")
    return hints

async def provide_hints_for_new_project(project_id: str, initial_query: str) -> List[Dict[str, Any]]:
    """Основная функция: ищет похожие проекты, извлекает подсказки, сохраняет в JSON."""
    logger.info(f"Searching hints for project {project_id} with query: {initial_query[:100]}")
    similar = await find_similar_projects(initial_query, limit=3)
    hints = []
    for proj in similar:
        proj_id = proj.get("id")
        if proj_id:
            hint_data = await extract_hints_from_project(proj_id)
            hints.append(hint_data)
    HINTS_DIR.mkdir(parents=True, exist_ok=True)
    hints_file = HINTS_DIR / f"{project_id}_hints.json"
    with open(hints_file, "w", encoding="utf-8") as f:
        json.dump({
            "project_id": project_id,
            "hints": hints,
            "generated_at": datetime.now().isoformat()
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Hints saved to {hints_file}")
    return hints