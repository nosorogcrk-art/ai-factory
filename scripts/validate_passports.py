#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_passports.py – проверяет YAML-шапку в паспортах веток (BR*/BR*.md)
и контейнеров (BR*/C*/C*.md).
"""

import sys
import yaml
from pathlib import Path

BRANCH_REQUIRED = {'id', 'name', 'responsible', 'status', 'containers'}
CONTAINER_REQUIRED = {'id', 'branch', 'name', 'responsible', 'status', 'dependencies'}

def validate_file(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return False, "Missing YAML frontmatter"
    parts = content.split('---', 2)
    if len(parts) < 3:
        return False, "Invalid frontmatter format"
    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as e:
        return False, f"YAML parse error: {e}"
    is_branch = file_path.parent.name.startswith('BR') and file_path.name.startswith('BR')
    is_container = file_path.parent.name.startswith('C') and file_path.name.startswith('C')
    if is_branch:
        missing = BRANCH_REQUIRED - set(data.keys())
        if missing:
            return False, f"Missing fields: {missing}"
        if not isinstance(data.get('containers'), list):
            return False, "containers must be a list"
        return True, None
    elif is_container:
        missing = CONTAINER_REQUIRED - set(data.keys())
        if missing:
            return False, f"Missing fields: {missing}"
        if not isinstance(data.get('dependencies'), list):
            return False, "dependencies must be a list"
        for opt in ('has_dockerfile', 'has_tests', 'healthcheck'):
            if opt in data and not isinstance(data[opt], bool):
                return False, f"{opt} must be boolean"
        return True, None
    else:
        return False, "Unknown file type"

def main():
    root = Path.cwd()
    branch_files = list(root.glob("BR*/BR*.md"))
    container_files = list(root.glob("BR*/C*/C*.md"))
    all_files = branch_files + container_files
    errors = []
    for file_path in all_files:
        ok, msg = validate_file(file_path)
        if not ok:
            errors.append(f"{file_path}: {msg}")
            print(f"❌ {file_path}: {msg}")
        else:
            print(f"✅ {file_path}")
    if errors:
        print(f"\n❌ Validation failed with {len(errors)} errors.")
        sys.exit(1)
    else:
        print(f"\n✅ All {len(all_files)} passports are valid.")
        sys.exit(0)

if __name__ == "__main__":
    main()