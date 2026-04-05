"""Бизнес-логика Packager."""
import os
import json
import logging
import subprocess
import shutil
import tempfile
import tarfile
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import httpx

logger = logging.getLogger(__name__)

BR18_URL = os.getenv("BR18_URL", "http://br18:8080/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"


def generate_metadata(version: str, skills: List[str]) -> dict:
    """Создаёт словарь метаданных продукта."""
    return {
        "product_version": version,
        "build_date": datetime.now().isoformat(),
        "skills": skills
    }


def build_docs(source_dir: Path, output_base: Path, version: str) -> Optional[Path]:
    """
    Собирает документацию MkDocs.

    Args:
        source_dir: Папка с исходниками документации (ожидается mkdocs.yml).
        output_base: Базовая папка для сохранения результатов.
        version: Версия продукта (используется в имени подпапки).

    Returns:
        Путь к собранной документации или None в случае ошибки/отсутствия конфига.
    """
    config_file = source_dir / "mkdocs.yml"
    if not config_file.exists():
        logger.info(f"MkDocs config not found at {config_file}, skipping docs generation")
        return None
    output_dir = output_base / f"docs-{version}"
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["mkdocs", "build", "-f", str(config_file), "-d", str(output_dir)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.info(f"Documentation built to {output_dir}")
        return output_dir
    except subprocess.CalledProcessError as e:
        logger.error(f"Documentation build failed: {e.stderr}")
        return None


def generate_release_notes(repo_path: Path, version: str, since_tag: Optional[str] = None, output_file: Optional[Path] = None) -> Optional[Path]:
    """
    Генерирует релиз-ноутсы на основе Git-коммитов.

    Args:
        repo_path: Путь к Git-репозиторию.
        version: Версия продукта (не используется в содержании, но сохраняется для единообразия).
        since_tag: Тег, от которого собирать коммиты (если None – все).
        output_file: Путь для сохранения файла (по умолчанию 02_ПРОДУКТ/РЕЛИЗЫ/RELEASE_NOTES.md).

    Returns:
        Путь к созданному файлу или None при ошибке.
    """
    if output_file is None:
        output_file = Path("02_ПРОДУКТ/РЕЛИЗЫ/RELEASE_NOTES.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        from git import Repo
    except ImportError:
        logger.error("GitPython not installed")
        return None
    try:
        repo = Repo(repo_path)
    except Exception as e:
        logger.error(f"Failed to open repo: {e}")
        return None
    if repo.bare:
        logger.error("Repository is bare or not a git repo")
        return None
    if since_tag:
        try:
            commits = list(repo.iter_commits(f"{since_tag}..HEAD"))
        except Exception:
            logger.error(f"Tag {since_tag} not found")
            return None
    else:
        commits = list(repo.iter_commits())
    import re
    task_pattern = re.compile(r'\b(IMP-\d{8}-\d{3}|P\d+\.\d+\.\d+)\b')
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("# Release Notes\n\n")
        for commit in commits:
            msg = commit.message.strip()
            if not msg:
                continue
            ids = task_pattern.findall(msg)
            if ids:
                f.write(f"- **{ids[0]}**: {msg.splitlines()[0]}\n")
            else:
                f.write(f"- {commit.hexsha[:7]}: {msg.splitlines()[0]}\n")
    logger.info(f"Release notes saved to {output_file}")
    return output_file


def create_archive(source_dir: Path, version: str, output_dir: Path) -> Path:
    """
    Создаёт tar.gz архив репозитория.

    Args:
        source_dir: Папка с содержимым для упаковки.
        version: Версия продукта (используется в имени архива).
        output_dir: Папка для сохранения архива.

    Returns:
        Путь к созданному архиву.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"product-{version}.tar.gz"
    archive_path = output_dir / archive_name

    def filter_archive(tarinfo):
        if any(part in tarinfo.name.split('/') for part in ['.git', '__pycache__', '.DS_Store']):
            return None
        return tarinfo

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name, filter=filter_archive)
    logger.info(f"Created archive {archive_path}")
    return archive_path


async def send_log_to_br18(event_type: str, details: dict):
    """Отправляет лог в BR18 асинхронно."""
    if not ENABLE_BR18:
        logger.info(f"BR18 stub: {event_type} {details}")
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                BR18_URL,
                json={
                    "timestamp": datetime.now().isoformat(),
                    "service": "C10.3",
                    "event_type": event_type,
                    "details": details
                },
                timeout=5.0
            )
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")


def package(repo_path: Path, version: str, skills: List[str]) -> tuple[bool, str]:
    """
    Основная функция упаковки продукта.

    Args:
        repo_path: Путь к репозиторию продукта.
        version: Версия продукта (если пусто, генерируется автоматически).
        skills: Список использованных навыков.

    Returns:
        Кортеж (успех, сообщение/путь к архиву).
    """
    try:
        if not repo_path.exists():
            return False, f"Repository path not found: {repo_path}"
        version = version or datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path("02_ПРОДУКТ/РЕЛИЗЫ")
        with tempfile.TemporaryDirectory(prefix="packager_") as tmpdir:
            tmp_path = Path(tmpdir)
            repo_copy = tmp_path / repo_path.name
            shutil.copytree(repo_path, repo_copy, ignore=shutil.ignore_patterns('.git', '__pycache__', '.DS_Store'))
            metadata = generate_metadata(version, skills)
            metadata_file = repo_copy / "metadata.json"
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            # Generate docs and release notes (optional)
            build_docs(repo_copy / "docs", output_dir, version)
            generate_release_notes(repo_copy, version, output_file=output_dir / "RELEASE_NOTES.md")
            archive_path = create_archive(repo_copy, version, output_dir)
            return True, str(archive_path)
    except Exception as e:
        logger.error(f"Packaging failed: {e}")
        return False, str(e)