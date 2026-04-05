#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rename_patches.py – переименовывает файлы патчей в папках BR*/C*/
в формат P<id>.md, извлекая ID из имени файла.
"""

import re
import shutil
import argparse
import logging
from pathlib import Path
from collections import defaultdict

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/rename_patches.log")
BACKUP_DIR = Path("backups_patches")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_patch_id_from_filename(filename: str) -> str:
    """Извлекает ID вида P<number> из имени файла."""
    match = re.search(r'(P\d+\.\d+\.\d+)', filename)
    return match.group(1) if match else None

def main():
    parser = argparse.ArgumentParser(description="Rename patch files to P<id>.md")
    parser.add_argument('--dry-run', action='store_true', help="Show changes without writing")
    parser.add_argument('--backup', action='store_true', help="Create backup before writing")
    parser.add_argument('--write', action='store_true', help="Actually rename files")
    args = parser.parse_args()

    if not args.write and not args.dry_run:
        print("Use --dry-run to preview changes, or --write to apply them.")
        return

    root = Path.cwd()
    # Все .md файлы в папках BR*/C*/
    all_md = list(root.glob("BR*/C*/*.md"))

    # Исключаем паспорта контейнеров (C*.md) и README
    candidates = [f for f in all_md if not f.name.startswith('C') and f.name != 'README.md']

    if not candidates:
        print("No candidate files found.")
        return

    print(f"Found {len(candidates)} candidate files.")

    conflicts = defaultdict(list)
    processed = 0

    for old_path in candidates:
        patch_id = extract_patch_id_from_filename(old_path.name)
        if not patch_id:
            print(f"Skipping {old_path}: cannot extract ID from filename")
            continue

        new_name = f"{patch_id}.md"
        new_path = old_path.parent / new_name

        if old_path.name == new_name:
            continue  # уже правильно назван

        if args.dry_run:
            print(f"Would rename: {old_path} -> {new_path}")
            processed += 1
            continue

        # Конфликт: целевой файл уже существует и это не тот же файл
        if new_path.exists() and new_path != old_path:
            conflicts[new_path].append(old_path)
            continue

        if args.backup:
            backup_path = BACKUP_DIR / old_path.relative_to(root)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(old_path, backup_path)
            logger.info(f"Backup created: {backup_path}")

        try:
            old_path.rename(new_path)
            print(f"Renamed: {old_path} -> {new_path}")
            logger.info(f"Renamed {old_path} -> {new_path}")
            processed += 1
        except Exception as e:
            print(f"Error renaming {old_path}: {e}")
            logger.error(f"Error renaming {old_path}: {e}")

    # Разрешаем конфликты добавлением суффикса
    if conflicts and not args.dry_run:
        print("\nResolving conflicts by adding suffixes:")
        for target, sources in conflicts.items():
            suffix = 1
            base = target.stem
            ext = target.suffix
            for src in sources:
                while True:
                    candidate = target.parent / f"{base}_{suffix}{ext}"
                    if not candidate.exists():
                        break
                    suffix += 1
                try:
                    src.rename(candidate)
                    print(f"  {src} -> {candidate}")
                    logger.info(f"Conflict resolved: {src} -> {candidate}")
                    processed += 1
                except Exception as e:
                    print(f"  Error renaming {src}: {e}")
                    logger.error(f"Error resolving conflict for {src}: {e}")

    if args.dry_run:
        print(f"Dry run completed. Would rename {processed} files.")
    else:
        print(f"Renamed {processed} files. Check logs at {LOG_FILE}")

if __name__ == "__main__":
    main()