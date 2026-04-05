#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import yaml
from pathlib import Path
import shutil
import sys

def extract_responsible(content):
    m = re.search(r'\*\*Ответственный:\*\*\s*([А-ЯЁA-Z]+(?:\s*/\s*[А-ЯЁA-Z]+)?)', content)
    if m:
        return m.group(1).strip()
    return None

def get_containers_for_branch(branch_dir):
    containers = []
    for c_dir in sorted(branch_dir.glob("C*/")):
        c_id = c_dir.name
        if c_id.startswith('C'):
            containers.append(c_id)
    return containers

def fix_branch_passport(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return
    parts = content.split('---', 2)
    if len(parts) < 3:
        return
    frontmatter = parts[1]
    body = parts[2]
    try:
        data = yaml.safe_load(frontmatter)
    except:
        return
    changed = False
    if 'containers' not in data:
        branch_dir = file_path.parent
        containers = get_containers_for_branch(branch_dir)
        data['containers'] = containers
        changed = True
    if 'responsible' not in data:
        resp = extract_responsible(body)
        if resp:
            data['responsible'] = resp
            changed = True
    if changed:
        new_frontmatter = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        new_content = f"---\n{new_frontmatter}---\n{body}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {file_path}")

def fix_container_passport(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        return
    parts = content.split('---', 2)
    if len(parts) < 3:
        return
    frontmatter = parts[1]
    body = parts[2]
    try:
        data = yaml.safe_load(frontmatter)
    except:
        return
    changed = False
    if 'dependencies' not in data:
        data['dependencies'] = []
        changed = True
    if 'responsible' not in data:
        resp = extract_responsible(body)
        if resp:
            data['responsible'] = resp
            changed = True
    if changed:
        new_frontmatter = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
        new_content = f"---\n{new_frontmatter}---\n{body}"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed {file_path}")

def main():
    root = Path.cwd()
    for branch_dir in root.glob("BR*/"):
        passport = branch_dir / f"{branch_dir.name}.md"
        if passport.exists():
            fix_branch_passport(passport)
        for container_dir in branch_dir.glob("C*/"):
            container_passport = container_dir / f"{container_dir.name}.md"
            if container_passport.exists():
                fix_container_passport(container_passport)

if __name__ == "__main__":
    main()