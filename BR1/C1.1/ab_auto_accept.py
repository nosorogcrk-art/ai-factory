import asyncio
import httpx
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

C19_4_URL = "http://ab-tester:8106"
SKILLS_BASE_DIR = Path("00_КАНОН/НАВЫКИ")
PROMPTS_BASE_DIR = Path("00_КАНОН/ПРОМПТЫ")

ACCEPTED_MARK_DIR = Path("01_ЦЕХ/МЕТРИКИ/ab_accepted")
ACCEPTED_MARK_DIR.mkdir(parents=True, exist_ok=True)

async def fetch_winning_experiments() -> list:
    """Запрашивает у C19.4 эксперименты с p_value < 0.05."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{C19_4_URL}/experiments/completed")
        resp.raise_for_status()
        data = resp.json()
        return data.get("experiments", [])

def is_experiment_processed(exp_id: str) -> bool:
    return (ACCEPTED_MARK_DIR / f"{exp_id}.done").exists()

def mark_experiment_processed(exp_id: str):
    (ACCEPTED_MARK_DIR / f"{exp_id}.done").touch()

def update_skill(skill_id: str, new_version_content: str):
    """
    Обновляет файл prompt.md навыка.
    Предполагается, что new_version_content – это полное содержимое файла prompt.md.
    """
    skill_dir = SKILLS_BASE_DIR / skill_id
    if not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory {skill_dir} not found")
    prompt_file = skill_dir / "prompt.md"
    # Создаём резервную копию
    backup_file = prompt_file.with_suffix(".md.bak")
    shutil.copy2(prompt_file, backup_file)
    # Записываем новую версию
    prompt_file.write_text(new_version_content, encoding="utf-8")
    logger.info(f"Updated skill {skill_id}: {prompt_file}")

def update_prompt(prompt_id: str, new_version_content: str):
    """Обновляет промпт (файл .md) в 00_КАНОН/ПРОМПТЫ/."""
    prompt_file = PROMPTS_BASE_DIR / f"{prompt_id}.md"
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file {prompt_file} not found")
    backup_file = prompt_file.with_suffix(".md.bak")
    shutil.copy2(prompt_file, backup_file)
    prompt_file.write_text(new_version_content, encoding="utf-8")
    logger.info(f"Updated prompt {prompt_id}: {prompt_file}")

async def apply_new_version(experiment: Dict[str, Any]) -> Dict[str, Any]:
    """
    Применяет победившую версию (обновляет файл навыка/промпта).
    Победитель определяется по сравнению treatment_rate и control_rate в result.
    """
    exp_id = experiment["id"]
    object_type = experiment["object_type"]
    object_id = experiment["object_id"]
    result = experiment["result"]
    treatment_rate = result.get("treatment_rate", 0)
    control_rate = result.get("control_rate", 0)
    if treatment_rate > control_rate:
        winner = "treatment"
        # Предполагается, что варианты хранятся в виде ["control", "treatment"]
        # и в контексте эксперимента есть поле "new_content" (или нужно его получить)
        # Упростим: будем считать, что в result есть поле "new_prompt_content" или "new_skill_content"
        new_content = result.get("new_content")
        if not new_content:
            raise ValueError("No new_content in experiment result")
    else:
        # Не должно произойти, т.к. improvement > 0, но на всякий случай
        winner = "control"
        new_content = None

    if not new_content:
        raise ValueError("Cannot determine new content")

    if object_type == "skill":
        update_skill(object_id, new_content)
    elif object_type == "prompt":
        update_prompt(object_id, new_content)
    else:
        raise ValueError(f"Unknown object_type: {object_type}")

    return {"status": "accepted", "winner": winner, "object_type": object_type, "object_id": object_id}

async def background_ab_accept():
    """Фоновый процесс: раз в час проверяет успешные эксперименты и применяет их."""
    while True:
        try:
            experiments = await fetch_winning_experiments()
            for exp in experiments:
                if not is_experiment_processed(exp["id"]):
                    await apply_new_version(exp)
                    mark_experiment_processed(exp["id"])
        except Exception as e:
            logger.error(f"AB auto-accept error: {e}")
        await asyncio.sleep(3600)   # 1 час