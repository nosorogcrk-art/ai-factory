#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_scanner.py – сканер спецификаций патчей
"""

import os
import re
import yaml
from pathlib import Path
from typing import List, Dict, Any
from logger import logger

def get_root_dir() -> Path:
    return Path(os.getenv("PROJECT_ROOT", Path.cwd()))

def load_patch_spec(spec_path: Path) -> Dict[str, Any]:
    try:
        with open(spec_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {spec_path}: {e}")
        raise

    if not content.startswith('---'):
        data = {'_path': str(spec_path)}
        match = re.search(r'P\d+\.\d+\.\d+', spec_path.name)
        if match:
            data['id'] = match.group()
        else:
            data['id'] = spec_path.stem
        logger.debug(f"No YAML frontmatter in {spec_path}, using filename as ID")
        return data

    parts = content.split('---', 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid frontmatter in {spec_path}")

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        logger.error(f"YAML error in {spec_path}: {e}")
        raise

    data['_path'] = str(spec_path)
    if 'id' not in data:
        match = re.search(r'P\d+\.\d+\.\d+', spec_path.name)
        if match:
            data['id'] = match.group()
        else:
            data['id'] = spec_path.stem
    return data

def scan_patches(root_dir: Path = None) -> List[Dict[str, Any]]:
    if root_dir is None:
        root_dir = get_root_dir()
    patches = []
    for spec_path in root_dir.glob("BR*/C*/P*.md"):
        try:
            data = load_patch_spec(spec_path)
            if data.get('id', '').startswith('P'):
                patches.append(data)
                logger.info(f"Loaded patch: {data['id']}")
        except Exception as e:
            logger.error(f"Error reading {spec_path}: {e}")
            continue
    logger.info(f"Found {len(patches)} patches")
    return patches

if __name__ == "__main__":
    patches = scan_patches()
    print(yaml.dump(patches, allow_unicode=True))