import logging
import subprocess
import re
from pathlib import Path
import repositories

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