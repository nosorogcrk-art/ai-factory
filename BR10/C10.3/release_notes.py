#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import sys
import logging
import re
from pathlib import Path
from git import Repo

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/release_notes.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def generate_notes(repo_path: Path, since_tag: str = None, output_file: Path = None):
    if output_file is None:
        output_file = Path("02_ПРОДУКТ/РЕЛИЗЫ/RELEASE_NOTES.md")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    try:
        repo = Repo(repo_path)
    except Exception as e:
        logging.error(f"Failed to open repo: {e}")
        return False

    if repo.bare:
        logging.error("Repository is bare or not a git repo")
        return False

    if since_tag:
        try:
            commits = list(repo.iter_commits(f"{since_tag}..HEAD"))
        except Exception:
            logging.error(f"Tag {since_tag} not found")
            return False
    else:
        commits = list(repo.iter_commits())

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
    logging.info(f"Release notes saved to {output_file}")
    return True

def main():
    data = json.load(sys.stdin)
    repo_path = Path(data.get("repo_path", "02_ПРОДУКТ/РЕПО"))
    since_tag = data.get("since_tag", None)
    output_file = Path(data.get("output_file", "02_ПРОДУКТ/РЕЛИЗЫ/RELEASE_NOTES.md"))

    if generate_notes(repo_path, since_tag, output_file):
        print(json.dumps({"status": "ok", "output": str(output_file)}))
    else:
        print(json.dumps({"status": "error"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
