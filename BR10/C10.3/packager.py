#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import logging
import tarfile
import shutil
import tempfile
from pathlib import Path
from datetime import datetime

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/packager.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def generate_metadata(version, skills_list=None):
    return {
        "product_version": version,
        "build_date": datetime.now().isoformat(),
        "skills": skills_list if skills_list else []
    }

def create_archive(source_dir: Path, version: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_name = f"product-{version}.tar.gz"
    archive_path = output_dir / archive_name

    def filter_archive(tarinfo):
        if any(part in tarinfo.name.split('/') for part in ['.git', '__pycache__', '.DS_Store']):
            return None
        return tarinfo

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name, filter=filter_archive)
    logging.info(f"Created archive {archive_path}")
    return archive_path

def main():
    data = json.load(sys.stdin)
    repo_path = Path(data.get("repo_path", "02_ПРОДУКТ/РЕПО"))
    version = data.get("version", datetime.now().strftime("%Y%m%d_%H%M%S"))
    output_dir = Path(data.get("output_dir", "02_ПРОДУКТ/РЕЛИЗЫ"))
    skills = data.get("skills", [])

    with tempfile.TemporaryDirectory(prefix="packager_") as tmpdir:
        tmp_path = Path(tmpdir)
        repo_copy = tmp_path / repo_path.name
        shutil.copytree(repo_path, repo_copy, ignore=shutil.ignore_patterns('.git', '__pycache__', '.DS_Store'))

        metadata = generate_metadata(version, skills)
        metadata_file = repo_copy / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        archive_path = create_archive(repo_copy, version, output_dir)
        print(json.dumps({"status": "ok", "archive": str(archive_path)}))

if __name__ == "__main__":
    main()
