#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Healthcheck для C7.1 Identity Core
Проверяет работоспособность prompt_builder.py
"""

import sys
import os
from pathlib import Path

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents/tools"))

try:
    from prompt_builder import get_prompt, PROMPT_DIR, HASH_FILE
    
    # Проверяем существование директории промптов
    if not PROMPT_DIR.exists():
        print(f"ERROR: Prompt directory not found: {PROMPT_DIR}")
        sys.exit(1)
    
    # Проверяем наличие хотя бы одного файла промпта
    prompt_files = list(PROMPT_DIR.glob("*.md"))
    if not prompt_files:
        print(f"ERROR: No prompt files found in {PROMPT_DIR}")
        sys.exit(1)
    
    # Пробуем получить промпт для первой найденной роли
    test_role = prompt_files[0].stem
    if test_role == "prompt_hashes":
        if len(prompt_files) > 1:
            test_role = prompt_files[1].stem
        else:
            print("ERROR: Only prompt_hashes.json found, no prompt files")
            sys.exit(1)
    
    prompt = get_prompt(test_role)
    
    if prompt is None:
        print(f"ERROR: Failed to get prompt for role {test_role}")
        sys.exit(1)
    
    # Проверяем, что промпт не пустой
    if not prompt.strip():
        print(f"ERROR: Empty prompt for role {test_role}")
        sys.exit(1)
    
    print(f"OK: C7.1 Identity Core is healthy")
    print(f"  - Prompt directory: {PROMPT_DIR} (exists)")
    print(f"  - Prompt files: {len(prompt_files)} found")
    print(f"  - Test role: {test_role} (success)")
    print(f"  - Hash file: {HASH_FILE} ({'exists' if HASH_FILE.exists() else 'not found'})")
    
    sys.exit(0)
    
except Exception as e:
    print(f"ERROR: Healthcheck failed: {e}")
    sys.exit(1)