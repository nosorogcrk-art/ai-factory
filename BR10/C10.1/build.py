#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build.py – автоматическая сборка продукта после интеграции.
"""

import json
import subprocess
import sys
import logging
from pathlib import Path

REPO_PATH = Path("02_ПРОДУКТ/РЕПО")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/build.log")
CONFIG_FILE = REPO_PATH / "build_config.json"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_config():
    if not CONFIG_FILE.exists():
        logging.error(f"Build config not found: {CONFIG_FILE}")
        return None
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to parse config: {e}")
        return None

def run_command(cmd, cwd=REPO_PATH):
    logging.info(f"Running: {cmd}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            capture_output=True,
            text=True,
            check=True
        )
        logging.info(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Command failed (exit {e.returncode}): {e.stderr}")
        return False

def main():
    config = load_config()
    if not config:
        sys.exit(1)

    commands = config.get("build_commands", [])
    if not commands:
        logging.warning("No build commands defined.")
        sys.exit(0)

    for cmd in commands:
        if not run_command(cmd):
            sys.exit(1)

    logging.info("Build completed successfully.")
    sys.exit(0)

if __name__ == "__main__":
    main()