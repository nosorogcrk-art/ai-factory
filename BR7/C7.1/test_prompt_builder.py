#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тесты для prompt_builder.py
"""

import os
import sys
import tempfile
import shutil
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

# Добавляем путь к модулю для импорта
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents/tools"))

from prompt_builder import (
    get_prompt, compute_hash, get_file_mtime, 
    load_hashes, save_hashes, init_hashes, send_log_to_br18
)

def test_compute_hash():
    """Тест вычисления хеша файла."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b"test content")
        temp_file = Path(f.name)
    
    try:
        hash_value = compute_hash(temp_file)
        # SHA256 от "test content"
        expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
        assert hash_value == expected, f"Expected {expected}, got {hash_value}"
        print("✓ test_compute_hash passed")
    finally:
        temp_file.unlink()

def test_get_file_mtime():
    """Тест получения времени модификации файла."""
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as f:
        f.write(b"test")
        temp_file = Path(f.name)
    
    try:
        mtime = get_file_mtime(temp_file)
        assert isinstance(mtime, float), f"mtime should be float, got {type(mtime)}"
        assert mtime > 0, f"mtime should be positive, got {mtime}"
        print("✓ test_get_file_mtime passed")
    finally:
        temp_file.unlink()

def test_load_save_hashes():
    """Тест загрузки и сохранения хешей."""
    with tempfile.TemporaryDirectory() as tmpdir:
        hash_file = Path(tmpdir) / "test_hashes.json"
        
        # Мокаем HASH_FILE
        with patch('prompt_builder.HASH_FILE', hash_file):
            # Тест 1: Загрузка несуществующего файла
            hashes = load_hashes()
            assert hashes == {}, f"Expected empty dict, got {hashes}"
            
            # Тест 2: Сохранение и загрузка
            test_data = {"test": {"hash": "abc", "mtime": 123.456}}
            save_hashes(test_data)
            
            hashes = load_hashes()
            assert hashes == test_data, f"Expected {test_data}, got {hashes}"
            
            print("✓ test_load_save_hashes passed")

def test_get_prompt_success():
    """Тест успешного получения промпта."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_dir = Path(tmpdir) / "prompts"
        prompt_dir.mkdir()
        
        # Создаем тестовый промпт
        prompt_file = prompt_dir / "TEST.md"
        prompt_content = "# РОЛЬ: TEST\n## 1. ПАСПОРТ РОЛИ\nTest content"
        prompt_file.write_text(prompt_content, encoding='utf-8')
        
        # Мокаем PROMPT_DIR и HASH_FILE
        with patch('prompt_builder.PROMPT_DIR', prompt_dir), \
             patch('prompt_builder.HASH_FILE', prompt_dir / "prompt_hashes.json"), \
             patch('prompt_builder.send_log_to_br18'):  # Мокаем отправку логов
            
            # Первый вызов должен инициализировать хеши
            result = get_prompt("TEST")
            assert result == prompt_content, f"Expected prompt content, got {result}"
            
            # Второй вызов должен использовать кэшированные хеши
            result2 = get_prompt("TEST")
            assert result2 == prompt_content
            
            print("✓ test_get_prompt_success passed")

def test_get_prompt_hash_mismatch():
    """Тест обнаружения несоответствия хеша при неизменном mtime."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_dir = Path(tmpdir) / "prompts"
        prompt_dir.mkdir()
        
        # Создаем тестовый промпт
        prompt_file = prompt_dir / "TEST.md"
        prompt_content = "# РОЛЬ: TEST\nOriginal content"
        prompt_file.write_text(prompt_content, encoding='utf-8')
        
        hash_file = prompt_dir / "prompt_hashes.json"
        
        # Мокаем PROMPT_DIR и HASH_FILE
        with patch('prompt_builder.PROMPT_DIR', prompt_dir), \
             patch('prompt_builder.HASH_FILE', hash_file), \
             patch('prompt_builder.send_log_to_br18'):
            
            # Инициализируем хеши с неправильным хешем, но текущим mtime
            current_mtime = get_file_mtime(prompt_file)
            hashes = {
                "TEST": {
                    "hash": "wrong_hash",  # Неправильный хеш
                    "mtime": current_mtime,  # Текущее время (файл не менялся)
                    "last_verified": "2026-01-01T00:00:00"
                }
            }
            save_hashes(hashes)
            
            # Должен вернуть None из-за несоответствия хеша при неизменном mtime
            result = get_prompt("TEST")
            assert result is None, f"Expected None for hash mismatch with same mtime, got {result}"
            
            print("✓ test_get_prompt_hash_mismatch passed")

def test_mtime_detection():
    """Тест обнаружения изменения файла по mtime."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_dir = Path(tmpdir) / "prompts"
        prompt_dir.mkdir()
        
        # Создаем тестовый промпт
        prompt_file = prompt_dir / "TEST.md"
        prompt_content = "# РОЛЬ: TEST\nOriginal content"
        prompt_file.write_text(prompt_content, encoding='utf-8')
        
        hash_file = prompt_dir / "prompt_hashes.json"
        
        # Мокаем PROMPT_DIR и HASH_FILE
        with patch('prompt_builder.PROMPT_DIR', prompt_dir), \
             patch('prompt_builder.HASH_FILE', hash_file), \
             patch('prompt_builder.send_log_to_br18'):
            
            # Инициализируем хеши
            result1 = get_prompt("TEST")
            assert result1 == prompt_content
            
            # Изменяем файл
            time.sleep(0.01)  # Небольшая задержка для изменения mtime
            new_content = "# РОЛЬ: TEST\nUpdated content"
            prompt_file.write_text(new_content, encoding='utf-8')
            
            # Должен обнаружить изменение и обновить хеш
            result2 = get_prompt("TEST")
            assert result2 == new_content, f"Expected updated content, got {result2}"
            
            # Проверяем, что хеш обновился
            hashes = load_hashes()
            assert hashes["TEST"]["hash"] == compute_hash(prompt_file)
            
            print("✓ test_mtime_detection passed")

def test_prompt_file_not_found():
    """Тест обработки отсутствующего файла промпта."""
    with tempfile.TemporaryDirectory() as tmpdir:
        prompt_dir = Path(tmpdir) / "prompts"
        prompt_dir.mkdir()
        
        with patch('prompt_builder.PROMPT_DIR', prompt_dir), \
             patch('prompt_builder.send_log_to_br18'):
            
            result = get_prompt("NONEXISTENT")
            assert result is None, f"Expected None for non-existent role, got {result}"
            
            print("✓ test_prompt_file_not_found passed")

def run_all_tests():
    """Запуск всех тестов."""
    print("Запуск тестов для prompt_builder.py...")
    print("=" * 50)
    
    tests = [
        test_compute_hash,
        test_get_file_mtime,
        test_load_save_hashes,
        test_get_prompt_success,
        test_get_prompt_hash_mismatch,
        test_mtime_detection,
        test_prompt_file_not_found,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"✗ {test.__name__} failed: {e}")
    
    print("=" * 50)
    print(f"Итог: {passed} пройдено, {failed} не пройдено")
    
    if failed == 0:
        print("✅ Все тесты пройдены успешно!")
        return 0
    else:
        print("❌ Некоторые тесты не пройдены")
        return 1

if __name__ == "__main__":
    sys.exit(run_all_tests())