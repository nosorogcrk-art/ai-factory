#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Интеграционные тесты API для C7.4 Skill Integrator
"""

import pytest
from fastapi.testclient import TestClient

from skill_integrator import app


class TestAPI:
    """Тесты API эндпоинтов"""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Тест эндпоинта /health"""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_compile_discovery_real(self):
        """
        Интеграционный тест для task_type="discovery".
        Проверяет, что эндпоинт возвращает корректную структуру.
        """
        response = self.client.post(
            "/compile",
            json={"task_type": "discovery"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем структуру ответа
        assert "prompt" in data
        assert "used_skills" in data
        assert "warnings" in data
        assert "total_matched" in data
        assert "returned" in data
        
        # Проверяем типы данных
        assert isinstance(data["prompt"], str)
        assert isinstance(data["used_skills"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["total_matched"], int)
        assert isinstance(data["returned"], int)
        
        # Если навык найден, проверяем содержимое
        if data["total_matched"] > 0:
            assert len(data["used_skills"]) == 1
            assert data["used_skills"][0] == "SKILL-DISCOVERY-001"
            assert len(data["prompt"]) > 0
            assert data["warnings"] == []
        else:
            # Если навык не найден
            assert data["prompt"] == ""
            assert data["used_skills"] == []
            assert "Skill discovery not found" in data["warnings"][0]
    
    @pytest.mark.asyncio
    async def test_compile_unknown_task_type(self):
        """Тест для неизвестного типа задачи"""
        response = self.client.post(
            "/compile",
            json={"task_type": "unknown_type_123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "STUB" in data["prompt"]
        assert data["used_skills"] == ["SKILL-UNKNOWN_TYPE_123"]
        assert len(data["warnings"]) == 1
        assert "not implemented" in data["warnings"][0]
        assert data["total_matched"] == 1
        assert data["returned"] == 1
    
    @pytest.mark.asyncio
    async def test_compile_with_required_skills(self):
        """Тест с явным указанием навыков"""
        response = self.client.post(
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
        """Тест ограничения количества навыков"""
        response = self.client.post(
            "/compile",
            json={
                "task_type": "discovery",
                "required_skills": ["SKILL-001", "SKILL-002", "SKILL-003", "SKILL-004"],
                "limit": 2
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["used_skills"]) == 2
        assert data["used_skills"] == ["SKILL-001", "SKILL-002"]
        assert data["total_matched"] == 2
        assert data["returned"] == 2
    
    @pytest.mark.asyncio
    async def test_compile_with_optional_fields(self):
        """Тест с опциональными полями (agent_type, language, context)"""
        response = self.client.post(
            "/compile",
            json={
                "task_type": "discovery",
                "agent_type": "main",
                "language": "python",
                "context": "Test context",
                "limit": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Проверяем, что ответ имеет правильную структуру
        assert "prompt" in data
        assert "used_skills" in data
        # Опциональные поля игнорируются в текущей реализации
    
    def test_invalid_request_missing_task_type(self):
        """Тест с отсутствующим обязательным полем task_type"""
        response = self.client.post(
            "/compile",
            json={}  # Отсутствует task_type
        )
        
        # FastAPI должен вернуть 422 (Unprocessable Entity) из-за валидации Pydantic
        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("task_type" in str(item).lower() for item in error_detail)
    
    def test_invalid_request_wrong_type(self):
        """Тест с некорректным типом данных"""
        response = self.client.post(
            "/compile",
            json={
                "task_type": 123,  # Должно быть строкой
                "limit": "invalid"  # Должно быть числом
            }
        )
        
        # FastAPI должен вернуть 422
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])