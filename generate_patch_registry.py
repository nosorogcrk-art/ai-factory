#!/usr/bin/env python3
"""
Генерирует реестр всех патчей Level 5, найденных в проекте.
Сохраняет в файл 00_КАНОН/Методология/реестр_патчей.json
"""
import json
import re
from pathlib import Path

SEARCH_PATHS = [
    Path("BR0"), Path("BR1"), Path("BR2"), Path("BR3"), Path("BR4"),
    Path("BR5"), Path("BR6"), Path("BR7"), Path("BR8"), Path("BR9"),
    Path("BR10"), Path("BR11"), Path("BR12"), Path("BR13"), Path("BR14"),
    Path("BR15"), Path("BR16"), Path("BR17"), Path("BR18"), Path("BR19"),
    Path("BR20"), Path(".")
]

def find_spec_files():
    spec_files = []
    for base in SEARCH_PATHS:
        if not base.exists():
            continue
        for file in base.rglob("*.md"):
            if "СПЕЦИФИКАЦИЯ ПАТЧА" in file.name or re.search(r'P\d+\.\d+\.\d+', file.name):
                spec_files.append(file)
            else:
                try:
                    with open(file, 'r', encoding='utf-8') as f:
                        content = f.read(1000)
                        if re.search(r'ID:\s*P\d+\.\d+\.\d+', content):
                            spec_files.append(file)
                except:
                    pass
    return spec_files

def extract_patch_id(file_path):
    match = re.search(r'(P\d+\.\d+\.\d+)', file_path.name)
    if match:
        return match.group(1)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read(500)
        match = re.search(r'ID:\s*(P\d+\.\d+\.\d+)', content)
        if match:
            return match.group(1)
    return None

def extract_dependencies(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "Зависимости" in line and ":" in line:
                deps = line.split(':', 1)[1].strip()
                if deps:
                    return re.findall(r'P\d+\.\d+\.\d+', deps)
                if i+1 < len(lines):
                    next_line = lines[i+1].strip()
                    if next_line and not next_line.startswith('#'):
                        return re.findall(r'P\d+\.\d+\.\d+', next_line)
        return []
    except:
        return []

def main():
    spec_files = find_spec_files()
    registry = {}
    for file in spec_files:
        pid = extract_patch_id(file)
        if not pid:
            continue
        deps = extract_dependencies(file)
        registry[pid] = {
            "file": str(file),
            "dependencies": deps,
            "status": "not_started"
        }
    sorted_registry = {k: registry[k] for k in sorted(registry.keys())}
    output_path = Path("00_КАНОН/Методология/реестр_патчей.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(sorted_registry, f, ensure_ascii=False, indent=2)
    print(f"✅ Реестр патчей создан: {output_path}")
    print(f"   Найдено патчей: {len(registry)}")

if __name__ == "__main__":
    main()
