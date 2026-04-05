#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
branch_scanner.py – сканер паспортов веток
"""

import os
import yaml
from pathlib import Path
from typing import List, Dict, Any
from logger import logger

def get_root_dir() -> Path:
    return Path(os.getenv("PROJECT_ROOT", Path.cwd()))

def load_branch_passport(passport_path: Path) -> Dict[str, Any]:
    try:
        with open(passport_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {passport_path}: {e}")
        raise

    if not content.startswith('---'):
        logger.warning(f"Missing YAML frontmatter in {passport_path}")
        raise ValueError(f"Missing YAML frontmatter in {passport_path}")

    parts = content.split('---', 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid frontmatter in {passport_path}")

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        logger.error(f"YAML error in {passport_path}: {e}")
        raise

    data['_path'] = str(passport_path)
    return data

def scan_branches(root_dir: Path = None) -> List[Dict[str, Any]]:
    if root_dir is None:
        root_dir = get_root_dir()
    branches = []
    for passport_path in root_dir.glob("BR*/BR*.md"):
        try:
            data = load_branch_passport(passport_path)
            if 'id' in data and data['id'].startswith('BR'):
                branches.append(data)
                logger.info(f"Loaded branch: {data['id']}")
        except Exception as e:
            logger.error(f"Error reading {passport_path}: {e}")
            continue
    logger.info(f"Found {len(branches)} branches")
    return branches

if __name__ == "__main__":
    branches = scan_branches()
    print(yaml.dump(branches, allow_unicode=True))