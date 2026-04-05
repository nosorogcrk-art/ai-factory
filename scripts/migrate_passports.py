#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
migrate_passports.py – добавляет YAML-шапку в паспорта веток (BR*/BR*.md)
и контейнеров (BR*/C*/C*.md).
"""

import re
import shutil
import argparse
import logging
from pathlib import Path
from collections import defaultdict

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/migrate_passports.log")
BACKUP_DIR = Path("backups")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_branch_fields(content: str) -> dict:
    fields = {}
    m = re.search(r'\*\*ID:\*\*\s*([A-Z0-9_.-]+)', content)
    if m:
        fields['id'] = m.group(1).strip()
    m = re.search(r'\*\*Ответственный:\*\*\s*([А-ЯЁA-Z]+(?:\s*/\s*[А-ЯЁA-Z]+)?)', content)
    if m:
        fields['responsible'] = m.group(1).strip()
    m = re.search(r'\*\*Статус:\*\*\s*(\w+)', content)
    if m:
        fields['status'] = m.group(1).strip()
    else:
        fields['status'] = 'active'
    m = re.search(r'### 📄 ПАСПОРТ ВЕТКИ\s+([A-Z0-9]+):\s*(.+?)(?:\n|$)', content)
    if m:
        fields['name'] = m.group(2).strip()
    else:
        fields['name'] = fields.get('id', 'Unknown')
    containers = []
    section_pattern = re.compile(r'##+\s*СОСТАВ УЗЛОВ \(L3\):.*?\n(.*?)(?=\n##|\Z)', re.DOTALL | re.IGNORECASE)
    section_match = section_pattern.search(content)
    if section_match:
        section_text = section_match.group(1)
        for match in re.finditer(r'^- \*\*([A-Z0-9.]+):', section_text, re.MULTILINE):
            containers.append(match.group(1).strip())
    fields['containers'] = containers
    return fields

def extract_container_fields(content: str, file_path: Path) -> dict:
    fields = {}
    # ID и ветка из пути
    match = re.search(r'BR([A-Z0-9]+)/C([0-9.]+)/C[0-9.]+\.md', str(file_path))
    if match:
        fields['id'] = f"C{match.group(2)}"
        fields['branch'] = f"BR{match.group(1)}"
    else:
        m = re.search(r'\*\*ID:\*\*\s*([A-Z0-9_.-]+)', content)
        if m:
            fields['id'] = m.group(1).strip()
        m = re.search(r'\*\*Ветка-родитель:\*\*\s*([A-Z0-9]+)', content)
        if m:
            fields['branch'] = m.group(1).strip()
    m = re.search(r'\*\*Ответственный:\*\*\s*([А-ЯЁA-Z]+(?:\s*/\s*[А-ЯЁA-Z]+)?)', content)
    if m:
        fields['responsible'] = m.group(1).strip()
    m = re.search(r'\*\*Статус:\*\*\s*(\w+)', content)
    if m:
        fields['status'] = m.group(1).strip()
    else:
        fields['status'] = 'planned'
    m = re.search(r'### \*\*C\d+\.\d+:\s*(.+?)\*\*', content)
    if m:
        fields['name'] = m.group(1).strip()
    else:
        fields['name'] = fields.get('id', 'Unknown')
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
    fields['dependencies'] = deps
    return fields

def generate_yaml_header(fields: dict) -> str:
    lines = ['---']
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, list):
            if not value:
                continue
            items = ', '.join(f'"{v}"' for v in value)
            lines.append(f'{key}: [{items}]')
        elif isinstance(value, bool):
            lines.append(f'{key}: {"true" if value else "false"}')
        else:
            lines.append(f'{key}: {value}')
    lines.append('---')
    return '\n'.join(lines)

def migrate_file(file_path: Path, dry_run: bool = False, backup: bool = False) -> bool:
    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return False
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if content.startswith('---'):
        logger.info(f"Skipping {file_path} – already has frontmatter")
        return False
    is_branch = file_path.parent.name.startswith('BR') and file_path.name.startswith('BR')
    is_container = file_path.parent.name.startswith('C') and file_path.name.startswith('C')
    if is_branch:
        fields = extract_branch_fields(content)
        if 'id' not in fields:
            fields['id'] = file_path.stem
    elif is_container:
        fields = extract_container_fields(content, file_path)
    else:
        logger.warning(f"Unknown file type: {file_path}")
        return False
    if not fields.get('id'):
        logger.error(f"Cannot determine ID for {file_path}")
        return False
    yaml_header = generate_yaml_header(fields)
    if backup and not dry_run:
        backup_path = BACKUP_DIR / file_path.relative_to(Path.cwd())
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(file_path, backup_path)
        logger.info(f"Backup created: {backup_path}")
    new_content = yaml_header + '\n\n' + content
    if dry_run:
        logger.info(f"[DRY RUN] Would update {file_path}")
        print(f"--- {file_path} ---")
        print(new_content[:500] + "...")
        return True
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    logger.info(f"Updated {file_path}")
    return True

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--backup', action='store_true')
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    if not args.write and not args.dry_run:
        print("Use --dry-run to preview changes, or --write to apply them.")
        return
    root = Path.cwd()
    branch_files = list(root.glob("BR*/BR*.md"))
    container_files = list(root.glob("BR*/C*/C*.md"))
    all_files = branch_files + container_files
    if not all_files:
        print("No passport files found.")
        return
    print(f"Found {len(all_files)} files to process.")
    modified = 0
    for file_path in all_files:
        if migrate_file(file_path, dry_run=args.dry_run, backup=args.backup):
            modified += 1
    if args.dry_run:
        print(f"Dry run completed. Would modify {modified} files.")
    else:
        print(f"Modified {modified} files. Check logs at {LOG_FILE}")

if __name__ == "__main__":
    main()