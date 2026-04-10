import logging
import subprocess
import re
from pathlib import Path
import repositories
import httpx
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

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

def build_patches(task_id: str, patch_ids: list[str], check_skills: bool, run_tests: bool) -> tuple[bool, str]:
    try:
        if check_skills:
            skills = _get_required_skills_from_patches(patch_ids)
            logger.info(f"Skills required for task {task_id}: {skills}")
        if not _apply_patches(patch_ids):
            return False, "Failed to apply patches"
        if not _run_build():
            return False, "Build failed"
        if task_id:
            repositories.update_task_status(task_id, "ON_REVIEW", "Build completed")
        return True, "Build started"
    except Exception as e:
        logger.error(f"Build process error: {e}")
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
