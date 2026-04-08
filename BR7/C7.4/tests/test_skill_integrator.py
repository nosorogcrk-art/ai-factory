#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Юнит-тесты для skill_integrator.py
"""

import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, AsyncMock, Mock

import httpx
import pytest

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skill_integrator import load_skill, _load_skill_prompt, _call_deepseek


class TestLoadSkill:
    """Тесты функции load_skill"""
    
    def setup_method(self):
        """Создаем временную директорию для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.skills_dir = Path(self.temp_dir) / "НАВЫКИ"
        self.skills_dir.mkdir(parents=True)
        
    def teardown_method(self):
        """Удаляем временную директорию"""
        shutil.rmtree(self.temp_dir)
    
    def test_load_skill_success(self):
        """Успешная загрузка навыка"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        skill_json = {
            "id": "SKILL-DISCOVERY-001",
            "name": "Test Skill",
            "version": "1.0"
        }
        
        prompt_content = "Test prompt content"
        
        # Создаем файлы
        (skill_dir / "skill.json").write_text(json.dumps(skill_json), encoding='utf-8')
        (skill_dir / "prompt.md").write_text(prompt_content, encoding='utf-8')
        
        # Мокаем SKILLS_BASE_PATH
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = load_skill(task_type)
        
        assert result['id'] == "SKILL-DISCOVERY-001"
        assert result['prompt'] == prompt_content
        assert result['skill_data'] == skill_json
    
    def test_load_skill_missing_json(self):
        """Отсутствует skill.json"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        # Создаем только prompt.md
        (skill_dir / "prompt.md").write_text("Test", encoding='utf-8')
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = load_skill(task_type)
        
        assert result == {}
    
    def test_load_skill_missing_prompt(self):
        """Отсутствует prompt.md"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        # Создаем только skill.json
        (skill_dir / "skill.json").write_text('{"id": "TEST"}', encoding='utf-8')
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = load_skill(task_type)
        
        assert result == {}
    
    def test_load_skill_invalid_json(self):
        """Некорректный JSON в skill.json"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        # Создаем файлы с некорректным JSON
        (skill_dir / "skill.json").write_text("invalid json", encoding='utf-8')
        (skill_dir / "prompt.md").write_text("Test", encoding='utf-8')
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = load_skill(task_type)
        
        assert result == {}
    
    def test_load_skill_missing_id(self):
        """В skill.json отсутствует поле id"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        skill_json = {
            "name": "Test Skill",
            "version": "1.0"
        }
        
        (skill_dir / "skill.json").write_text(json.dumps(skill_json), encoding='utf-8')
        (skill_dir / "prompt.md").write_text("Test", encoding='utf-8')
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = load_skill(task_type)
        
        assert result['id'] == "UNKNOWN-discovery"
        assert result['prompt'] == "Test"


class TestCompileEndpoint:
    """Тесты эндпоинта /compile через моки"""
    
    @pytest.mark.asyncio
    async def test_compile_discovery_success(self):
        """Успешный запрос для task_type='discovery'"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        # Мокаем load_skill
        mock_skill = {
            'id': 'SKILL-DISCOVERY-001',
            'prompt': 'Test prompt content',
            'skill_data': {'id': 'SKILL-DISCOVERY-001'}
        }
        
        with patch('skill_integrator.load_skill', return_value=mock_skill):
            client = TestClient(app)
            response = client.post(
                "/compile",
                json={"task_type": "discovery"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == "Test prompt content"
        assert data["used_skills"] == ["SKILL-DISCOVERY-001"]
        assert data["warnings"] == []
        assert data["total_matched"] == 1
        assert data["returned"] == 1
    
    @pytest.mark.asyncio
    async def test_compile_discovery_not_found(self):
        """Навык discovery не найден"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        with patch('skill_integrator.load_skill', return_value={}):
            client = TestClient(app)
            response = client.post(
                "/compile",
                json={"task_type": "discovery"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["prompt"] == ""
        assert data["used_skills"] == []
        assert data["warnings"] == ["Skill discovery not found"]
        assert data["total_matched"] == 0
        assert data["returned"] == 0
    
    @pytest.mark.asyncio
    async def test_compile_unknown_task_type(self):
        """Неизвестный task_type возвращает заглушку"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post(
            "/compile",
            json={"task_type": "unknown"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "STUB" in data["prompt"]
        assert data["used_skills"] == ["SKILL-UNKNOWN"]
        assert len(data["warnings"]) == 1
        assert "not implemented" in data["warnings"][0]
        assert data["total_matched"] == 1
        assert data["returned"] == 1
    
    @pytest.mark.asyncio
    async def test_compile_with_required_skills(self):
        """Запрос с required_skills возвращает заглушку"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post(
            "/compile",
            json={
                "task_type": "discovery",
                "required_skills": ["SKILL-001", "SKILL-002"],
                "limit": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "Explicit skill selection not yet implemented" in data["prompt"]
        assert data["used_skills"] == ["SKILL-001", "SKILL-002"]
        assert data["warnings"] == ["Explicit skill selection is a stub"]
        assert data["total_matched"] == 2
        assert data["returned"] == 2
    
    @pytest.mark.asyncio
    async def test_compile_with_limit(self):
        """Проверка ограничения limit"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post(
            "/compile",
            json={
                "task_type": "discovery",
                "required_skills": ["SKILL-001", "SKILL-002", "SKILL-003"],
                "limit": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["used_skills"]) == 2
        assert data["used_skills"] == ["SKILL-001", "SKILL-002"]


class TestLoadSkillPrompt:
    """Тесты функции _load_skill_prompt"""
    
    def setup_method(self):
        """Создаем временную директорию для тестов"""
        self.temp_dir = tempfile.mkdtemp()
        self.skills_dir = Path(self.temp_dir) / "НАВЫКИ"
        self.skills_dir.mkdir(parents=True)
        
    def teardown_method(self):
        """Удаляем временную директорию"""
        shutil.rmtree(self.temp_dir)
    
    def test_load_skill_prompt_success(self):
        """Успешная загрузка промпта навыка"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        prompt_content = "Test prompt content"
        (skill_dir / "prompt.md").write_text(prompt_content, encoding='utf-8')
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = _load_skill_prompt(task_type)
        
        assert result == prompt_content
    
    def test_load_skill_prompt_not_found(self):
        """Промпт навыка не найден"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        # Не создаем prompt.md
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = _load_skill_prompt(task_type)
        
        assert result is None
    
    def test_load_skill_prompt_read_error(self):
        """Ошибка при чтении файла"""
        task_type = "discovery"
        skill_dir = self.skills_dir / task_type
        skill_dir.mkdir()
        
        # Создаем директорию вместо файла, чтобы вызвать ошибку
        (skill_dir / "prompt.md").mkdir()
        
        with patch('skill_integrator.SKILLS_BASE_PATH', Path(self.temp_dir) / "НАВЫКИ"):
            result = _load_skill_prompt(task_type)
        
        assert result is None


class TestCallDeepSeek:
    """Тесты функции _call_deepseek"""
    
    @pytest.mark.asyncio
    async def test_call_deepseek_success(self):
        """Успешный вызов DeepSeek API"""
        system_prompt = "System prompt"
        user_prompt = '{"test": "data"}'
        
        mock_response = {
            "choices": [{
                "message": {
                    "content": '{"result": "success", "data": {"key": "value"}}'
                }
            }]
        }
        
        with patch('skill_integrator.DEEPSEEK_API_KEY', 'test-key'), \
             patch('skill_integrator.httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = Mock()
            mock_client.post.return_value = mock_response_obj
            
            result = await _call_deepseek(system_prompt, user_prompt)
        
        assert result == {"result": "success", "data": {"key": "value"}}
    
    @pytest.mark.asyncio
    async def test_call_deepseek_no_api_key(self):
        """Отсутствует API-ключ"""
        with patch('skill_integrator.DEEPSEEK_API_KEY', ''):
            result = await _call_deepseek("system", "user")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_call_deepseek_http_error(self):
        """Ошибка HTTP при вызове API"""
        with patch('skill_integrator.DEEPSEEK_API_KEY', 'test-key'), \
             patch('skill_integrator.httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_client.post.side_effect = httpx.HTTPError("HTTP error")
            
            result = await _call_deepseek("system", "user")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_call_deepseek_empty_response(self):
        """Пустой ответ от API"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": ""
                }
            }]
        }
        
        with patch('skill_integrator.DEEPSEEK_API_KEY', 'test-key'), \
             patch('skill_integrator.httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = Mock()
            mock_client.post.return_value = mock_response_obj
            
            result = await _call_deepseek("system", "user")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_call_deepseek_non_json_response(self):
        """Ответ не в формате JSON"""
        mock_response = {
            "choices": [{
                "message": {
                    "content": "Just plain text response"
                }
            }]
        }
        
        with patch('skill_integrator.DEEPSEEK_API_KEY', 'test-key'), \
             patch('skill_integrator.httpx.AsyncClient') as mock_client_class:
            mock_client = mock_client_class.return_value.__aenter__.return_value
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 200
            mock_response_obj.json = AsyncMock(return_value=mock_response)
            mock_response_obj.raise_for_status = Mock()
            mock_client.post.return_value = mock_response_obj
            
            result = await _call_deepseek("system", "user")
        
        assert result == {"text": "Just plain text response"}


class TestExecuteEndpoint:
    """Тесты эндпоинта /execute"""
    
    @pytest.mark.asyncio
    async def test_execute_skill_success(self):
        """Успешное выполнение навыка"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        mock_prompt = "System prompt content"
        mock_llm_response = {"result": "success", "data": {"key": "value"}}
        
        with patch('skill_integrator._load_skill_prompt', return_value=mock_prompt), \
             patch('skill_integrator._call_deepseek', return_value=mock_llm_response), \
             patch('skill_integrator.SKILLS_BASE_PATH', Path("/tmp/test")), \
             patch('skill_integrator.os.path.exists', return_value=True), \
             patch('builtins.open', create=True) as mock_open:
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.read.return_value = '{"id": "SKILL-TEST-001"}'
            
            client = TestClient(app)
            response = client.post(
                "/execute",
                json={
                    "task_type": "discovery",
                    "context": {"test": "data"}
                }
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["result"] == mock_llm_response
        assert data["skill_id"] == "SKILL-TEST-001"
        assert data["warnings"] == []
    
    @pytest.mark.asyncio
    async def test_execute_skill_not_found(self):
        """Навык не найден"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        with patch('skill_integrator._load_skill_prompt', return_value=None):
            client = TestClient(app)
            response = client.post(
                "/execute",
                json={
                    "task_type": "unknown",
                    "context": {"test": "data"}
                }
            )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Skill 'unknown' not found" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_execute_skill_llm_error(self):
        """Ошибка при вызове LLM"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        mock_prompt = "System prompt content"
        
        with patch('skill_integrator._load_skill_prompt', return_value=mock_prompt), \
             patch('skill_integrator._call_deepseek', return_value=None):
            client = TestClient(app)
            response = client.post(
                "/execute",
                json={
                    "task_type": "discovery",
                    "context": {"test": "data"}
                }
            )
        
        assert response.status_code == 502
        data = response.json()
        assert "detail" in data
        assert "LLM call failed" in data["detail"]
    
    @pytest.mark.asyncio
    async def test_execute_skill_no_context(self):
        """Запрос без контекста должен вернуть 422 (валидация)"""
        from skill_integrator import app
        from fastapi.testclient import TestClient
        
        client = TestClient(app)
        response = client.post(
            "/execute",
            json={
                "task_type": "discovery"
                # отсутствует обязательное поле context
            }
        )
        
        assert response.status_code == 422  # Unprocessable Entity
        data = response.json()
        assert "detail" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
