#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
map_generator.py – сбор всех данных в единую карту
"""

import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
from branch_scanner import scan_branches, get_root_dir
from container_scanner import scan_containers
from patch_scanner import scan_patches
from logger import logger

def get_output_path() -> Path:
    root = get_root_dir()
    return root / "SYSTEM_MAP.json"

def generate_map(root_dir: Path = None) -> Dict[str, Any]:
    if root_dir is None:
        root_dir = get_root_dir()
    logger.info("Generating system map...")
    branches = scan_branches(root_dir)
    containers = scan_containers(root_dir)
    patches = scan_patches(root_dir)

    total_containers = len(containers)
    implemented_containers = sum(1 for c in containers if c.get('status') == 'implemented')
    containers_with_tests = sum(1 for c in containers if c.get('has_tests'))
    containers_with_healthcheck = sum(1 for c in containers if c.get('healthcheck'))

    stats = {
        'total_branches': len(branches),
        'total_containers': total_containers,
        'total_patches': len(patches),
        'implemented_containers': implemented_containers,
        'containers_with_tests': containers_with_tests,
        'containers_with_healthcheck': containers_with_healthcheck,
    }

    map_data = {
        'generated_at': datetime.now().isoformat(),
        'version': '1.0',
        'branches': branches,
        'containers': containers,
        'patches': patches,
        'stats': stats,
    }
    logger.info(f"Map generated: {stats}")
    return map_data

def save_map(map_data: Dict[str, Any], output_path: Path = None):
    if output_path is None:
        output_path = get_output_path()
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Map saved to {output_path}")
    except Exception as e:
        logger.error(f"Failed to save map: {e}")
        raise

def refresh_map(output_path: Path = None) -> Dict[str, Any]:
    if output_path is None:
        output_path = get_output_path()
    map_data = generate_map()
    save_map(map_data, output_path)
    return map_data

if __name__ == "__main__":
    map_data = generate_map()
    save_map(map_data)
    print(f"Saved to {get_output_path()}")