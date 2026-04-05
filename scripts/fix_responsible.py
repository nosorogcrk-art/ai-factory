#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import yaml
from pathlib import Path

# Словарь контейнеров, где нужно добавить ответственного
fix_map = {
    "BR19/C19.4": "ДЕДАЛ",
    "BR19/C19.3": "ДЕДАЛ",
    "BR19/C19.2": "ДЕДАЛ",
    "BR18/C18.1": "ГЕРМЕС",
    "BR18/C18.5": "ГЕРМЕС",
    "BR4/C4.3": "АРХИ / ГЕФЕСТ",
    "BR4/C4.2": "АРХИ / ГЕФЕСТ",
}

root = Path.cwd()
for rel_path, responsible in fix_map.items():
    file_path = root / rel_path / f"{Path(rel_path).name}.md"
    if not file_path.exists():
        print(f"File not found: {file_path}")
        continue
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    if not content.startswith('---'):
        print(f"No frontmatter in {file_path}")
        continue
    parts = content.split('---', 2)
    if len(parts) < 3:
        print(f"Invalid frontmatter in {file_path}")
        continue
    frontmatter = parts[1]
    body = parts[2]
    try:
        data = yaml.safe_load(frontmatter)
    except Exception as e:
        print(f"YAML error in {file_path}: {e}")
        continue
    if 'responsible' in data:
        print(f"{file_path} already has responsible: {data['responsible']}")
        continue
    data['responsible'] = responsible
    new_frontmatter = yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False)
    new_content = f"---\n{new_frontmatter}---\n{body}"
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print(f"Fixed {file_path}")