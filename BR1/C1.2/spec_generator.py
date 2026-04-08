#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
spec_generator.py – генерация спецификаций L5 для патчей.
"""

import json
import sys
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

TASK_REGISTRY_PATH = Path("01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json")
TEMPLATE_PATH = Path("00_КАНОН/Методология/ШАБЛОНЫ/ШАБЛОН_L5.md")
SPEC_DIR = Path("01_ЦЕХ/ЧЕРНОВИКИ/СПЕКИ/")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/spec_generator.log")

SPEC_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_json(path: Path, default: Any) -> Any:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def load_template() -> str:
    if not TEMPLATE_PATH.exists():
        # Заглушка, если шаблона нет – создаём минимальный
        return """# СПЕЦИФИКАЦИЯ ПАТЧА {{PATCH_ID}}

## 1. ЗАМЫСЕЛ
{{DESCRIPTION}}

## 2. ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ
*Будут уточнены в процессе реализации.*

## 3. РЕАЛИЗАЦИЯ
*Код и описание изменений.*

## 4. КРИТЕРИЙ ПРИЕМКИ (DoD)
*Условия завершения патча.*

## 5. ИСТОРИЯ ИЗМЕНЕНИЙ
- {{DATE}}: Создана спецификация.
"""
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def generate_spec(task: Dict[str, Any], template: str) -> str:
    """Генерирует спецификацию L5 для задачи."""
    content = template.replace("{{PATCH_ID}}", task["id"])
    content = content.replace("{{TITLE}}", task.get("title", ""))
    content = content.replace("{{DESCRIPTION}}", task.get("description", ""))
    content = content.replace("{{DATE}}", datetime.now().strftime("%Y-%m-%d"))

    # Добавляем раздел ТРЕБУЕМЫЕ НАВЫКИ, если есть
    skills = task.get("required_skills", [])
    if skills:
        skills_section = "\n## ТРЕБУЕМЫЕ НАВЫКИ\n"
        for s in skills:
            skills_section += f"- [[{s}]]\n"
        # Вставляем после раздела "1. ЗАМЫСЕЛ"
        if "## 1. ЗАМЫСЕЛ" in content:
            content = content.replace("## 1. ЗАМЫСЕЛ", "## 1. ЗАМЫСЕЛ" + skills_section)
        else:
            # Если не нашли, добавляем перед "## 2. ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ"
            content = content.replace("## 2. ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ", skills_section + "## 2. ТЕХНИЧЕСКИЕ ПАРАМЕТРЫ")
    return content


def main() -> None:
    registry = load_json(TASK_REGISTRY_PATH, [])
    template = load_template()

    # Определяем, какие патчи обрабатывать
    target_ids = sys.argv[1:] if len(sys.argv) > 1 else None

    generated = 0
    for task in registry:
        if task.get("type") != "improvement":
            continue
        if target_ids and task["id"] not in target_ids:
            continue
        spec_file = SPEC_DIR / f"{task['id']}.md"
        if spec_file.exists():
            logger.info(f"Spec for {task['id']} already exists, skipping.")
            continue
        spec_content = generate_spec(task, template)
        with open(spec_file, "w", encoding="utf-8") as f:
            f.write(spec_content)
        logger.info(f"Generated spec for {task['id']}")
        generated += 1

    print(json.dumps({"status": "ok", "generated": generated}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()