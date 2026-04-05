#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
versioning.py – создание тега и архива продукта после успешной сборки.
"""

import argparse
import json
import subprocess
import sys
import logging
from pathlib import Path
from datetime import datetime

REPO_PATH = Path("02_ПРОДУКТ/РЕПО")
RELEASES_DIR = Path("02_ПРОДУКТ/РЕЛИЗЫ")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/versioning.log")
VERSION_FILE = REPO_PATH / "version.txt"

RELEASES_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def run_git(cmd, cwd=REPO_PATH):
    try:
        subprocess.run(["git"] + cmd, cwd=cwd, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Git error: {e.stderr.decode()}")
        return False

def get_version():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Product version (overrides version.txt)")
    args, _ = parser.parse_known_args()
    if args.version:
        return args.version
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text().strip()
    return datetime.now().strftime("%Y%m%d-%H%M%S")

def create_unique_tag(base_version):
    tag = f"v{base_version}"
    counter = 1
    while True:
        existing = subprocess.run(
            ["git", "tag", "-l", tag],
            cwd=REPO_PATH,
            capture_output=True,
            text=True
        )
        if not existing.stdout.strip():
            break
        counter += 1
        tag = f"v{base_version}-{counter}"
    if run_git(["tag", tag]):
        logging.info(f"Created tag {tag}")
        return tag
    return None

def create_archive(version):
    archive_name = f"product-{version}.tar.gz"
    archive_path = RELEASES_DIR / archive_name
    if not REPO_PATH.exists() or not (REPO_PATH / ".git").exists():
        logging.error(f"Not a git repository: {REPO_PATH}")
        return None
    cmd = f"tar -czf {archive_path} --exclude=.git -C {REPO_PATH} ."
    try:
        subprocess.run(cmd, shell=True, check=True, capture_output=True)
        logging.info(f"Created archive {archive_path}")
        return archive_path
    except subprocess.CalledProcessError as e:
        logging.error(f"Archive creation failed: {e.stderr}")
        return None

def main():
    if not (REPO_PATH / ".git").exists():
        logging.error(f"Not a git repository: {REPO_PATH}")
        sys.exit(1)

    version = get_version()
    tag = create_unique_tag(version)
    if not tag:
        sys.exit(1)

    archive = create_archive(version)
    if not archive:
        sys.exit(1)

    print(json.dumps({"version": version, "tag": tag, "archive": str(archive)}))

if __name__ == "__main__":
    main()