#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_passports.py – добавляет недостающие поля в YAML-шапку паспортов:
- для веток: containers (из раздела СОСТАВ УЗЛОВ)
- для контейнеров: dependencies (из раздела ИНТЕГРАЦИИ)
"""

import re
import yaml
import sys
from pathlib import Path
from collections import defaultdict

def extract_containers_from_branch(content):
    """Извлекает список ID контейнеров из раздела СОСТАВ УЗЛОВ (L3)"""
    containers = []
    # Ищем раздел СОСТАВ УЗЛОВ (L3):
    section_pattern = re.compile(r'##+\s*СОСТАВ УЗЛОВ \(L3\):.*?\n(.*?)(?=\n##|\Z)', re.DOTALL | re.IGNORECASE)
    section_match = section_pattern.search(content)
    if section_match:
        section_text = section_match.group(1)
        # Ищем строки вида "- **C1.2:**"
        for match in re.finditer(r'^- \*\*([A-Z0-9.]+):', section_text, re.MULTILINE):
            containers.append(match.group(1).strip())
    return containers

def extract_dependencies_from_container(content):
    """Извлекает список ID контейнеров, от которых зависит данный контейнер, из разделов ИНТЕГРАЦИИ, СВЯЗИ, ЗАВИСИМОСТИ"""
    deps = []
    for section_title in ['ИНТЕГРАЦИИ', 'СВЯЗИ', 'ЗАВИСИМОСТИ']:
        section_pattern = re.compile(rf'##+\s*{section_title}.*?\n(.*?)(?=\n##|\Z)', re.DOTALL | re.IGNORECASE)
        section_match = section_pattern.search(content)
        if section_match:
            section_text = section_match.group(1)
            for match in re.finditer(r'^-\s+(?:\*\*)?([A-Z0-9.]+)(?:\*\*)?', section_text, re.MULTILINE):
                dep = match.group(1).strip()
                if dep not in deps:
                    deps.append(dep)
    return deps

def extract_responsible_from_content(content):
    """Извлекает ответственного из текста"""
    m = re.search(r'\*\*Ответственный:\*\*\s*([А-ЯЁA-Z]+(?:\s*/\s*[А-ЯЁA-Z]+)?)', content)
    if m:
        return m.group(1).strip()
    return None

def main():
    root = Path.cwd()
    branch_files = list(root.glob("BR*/BR*.md"))
    container_files = list(root.glob("BR*/C*/C*.md"))
    all_files = branch_files + container_files

    for file_path in all_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if not content.startswith('---'):
            print(f"Skipping {file_path}: no frontmatter")
            continue

        # Разделяем YAML-шапку и тело
        parts = content.split('---', 2)
        if len(parts) < 3:
            print(f"Skipping {file_path}: invalid frontmatter")
            continue

        yaml_str = parts[1]
        body = parts[2]

        try:
            data = yaml.safe_load(yaml_str)
        except yaml.YAMLError as e:
            print(f"Error parsing YAML in {file_path}: {e}")
            continue

        modified = False

        # Определяем тип
        is_branch = file_path.parent.name.startswith('BR') and file_path.name.startswith('BR')
        is_container = file_path.parent.name.startswith('C') and file_path.name.startswith('C')

        if is_branch:
            if 'containers' not in data or not data['containers']:
                containers = extract_containers_from_branch(body)
                if containers:
                    data['containers'] = containers
                    modified = True
                    print(f"Added containers to {file_path}: {containers}")
        elif is_container:
            if 'dependencies' not in data or not data['dependencies']:
                deps = extract_dependencies_from_container(body)
                if deps:
                    data['dependencies'] = deps
                    modified = True
                    print(f"Added dependencies to {file_path}: {deps}")
            if 'responsible' not in data or not data['responsible']:
                resp = extract_responsible_from_content(body)
                if resp:
                    data['responsible'] = resp
                    modified = True
                    print(f"Added responsible to {file_path}: {resp}")

        if modified:
            new_yaml = yaml.dump(data, allow_unicode=True, sort_keys=False)
            new_content = f"---\n{new_yaml}---\n{body}"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {file_path}")

if __name__ == "__main__":
    main()