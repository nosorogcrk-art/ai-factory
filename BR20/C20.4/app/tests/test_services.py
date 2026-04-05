"""
Тесты для сервисов C20.4 Test Runner
"""

import pytest
import json
import yaml
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.test_service import TestService
from app.models.config import TestRequest, TestType, TestStatus


class TestTestService:
    """Тесты для TestService"""
    
    @pytest.fixture
    def test_service(self):
        """Фикстура для создания экземпляра TestService"""
        service = TestService()
        yield service
        # Очистка после тестов
        service.active_tests.clear()
    
    @pytest.fixture
    def test_request(self):
        """Фикстура для создания тестового запроса"""
        return TestRequest(
            repo="test-repo",
            commit="abc123",
            tests=[TestType.SYNTAX, TestType.SEMANTIC]
        )
    
    @pytest.mark.asyncio
    async def test_run_tests(self, test_service, test_request):
        """Тест запуска тестов"""
        # Запускаем тесты
        response = await test_service.run_tests(test_request)
        
        # Проверяем ответ
        assert response.test_id.startswith("tst_")
        assert response.status == TestStatus.PENDING
        assert response.repo == "test-repo"
        assert response.commit == "abc123"
        assert TestType.SYNTAX in response.tests
        assert TestType.SEMANTIC in response.tests
        
        # Проверяем, что тест сохранен в активных тестах
        assert response.test_id in test_service.active_tests
    
    @pytest.mark.asyncio
    async def test_get_test_results(self, test_service, test_request):
        """Тест получения результатов тестов"""
        # Создаем тест
        response = await test_service.run_tests(test_request)
        test_id = response.test_id
        
        # Получаем результаты
        results = await test_service.get_test_results(test_id)
        
        # Проверяем результаты
        assert results is not None
        assert results.test_id == test_id
        assert results.status == TestStatus.PENDING
        assert not results.passed
        
        # Проверяем, что есть результаты для всех типов тестов
        assert TestType.SYNTAX in results.results
        assert TestType.SEMANTIC in results.results
    
    @pytest.mark.asyncio
    async def test_get_test_results_not_found(self, test_service):
        """Тест получения результатов несуществующего теста"""
        results = await test_service.get_test_results("nonexistent")
        assert results is None
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_valid_json(self, test_service):
        """Тест синтаксических тестов с валидным JSON"""
        files = [
            {
                "path": "test.json",
                "content": '{"name": "test", "value": 42}'
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.json"
        assert results[0].valid is True
        assert len(results[0].errors) == 0
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_invalid_json(self, test_service):
        """Тест синтаксических тестов с невалидным JSON"""
        files = [
            {
                "path": "test.json",
                "content": '{"name": "test", "value": 42'
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.json"
        assert results[0].valid is False
        assert len(results[0].errors) > 0
        assert "JSON parsing error" in results[0].errors[0]
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_valid_yaml(self, test_service):
        """Тест синтаксических тестов с валидным YAML"""
        files = [
            {
                "path": "test.yaml",
                "content": "name: test\nvalue: 42"
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.yaml"
        assert results[0].valid is True
        assert len(results[0].errors) == 0
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_invalid_yaml(self, test_service):
        """Тест синтаксических тестов с невалидным YAML"""
        files = [
            {
                "path": "test.yaml",
                "content": "name: test\n  value: 42"
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.yaml"
        assert results[0].valid is False
        assert len(results[0].errors) > 0
        assert "YAML parsing error" in results[0].errors[0]
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_empty_file(self, test_service):
        """Тест синтаксических тестов с пустым файлом"""
        files = [
            {
                "path": "test.txt",
                "content": ""
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.txt"
        assert results[0].valid is False
        assert "File is empty" in results[0].errors[0]
    
    @pytest.mark.asyncio
    async def test_execute_syntax_tests_non_empty_text(self, test_service):
        """Тест синтаксических тестов с непустым текстовым файлом"""
        files = [
            {
                "path": "test.txt",
                "content": "Some text content"
            }
        ]
        
        results = await test_service.execute_syntax_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.txt"
        assert results[0].valid is True
        assert len(results[0].errors) == 0
    
    @pytest.mark.asyncio
    async def test_execute_semantic_tests(self, test_service):
        """Тест семантических тестов (заглушка)"""
        files = [
            {
                "path": "test.json",
                "content": '{"name": "test"}'
            }
        ]
        
        results = await test_service.execute_semantic_tests(files)
        
        assert len(results) == 1
        assert results[0].file_path == "test.json"
        assert results[0].valid is True
        assert len(results[0].missing_references) == 0
        assert len(results[0].duplicate_ids) == 0
    
    @pytest.mark.asyncio
    async def test_execute_functional_tests(self, test_service):
        """Тест функциональных тестов (заглушка)"""
        files = [
            {
                "path": "skill_test.json",
                "content": '{"skill": "test"}'
            }
        ]
        
        results = await test_service.execute_functional_tests(files)
        
        assert len(results) == 1
        assert results[0].test_name == "Skill test for skill_test.json"
        assert results[0].passed is True
        assert "Skill test passed (stub)" in results[0].output
    
    @pytest.mark.asyncio
    async def test_health_check(self, test_service):
        """Тест проверки здоровья сервиса"""
        is_healthy = await test_service.health_check()
        assert is_healthy is True
    
    @pytest.mark.asyncio
    async def test_close(self, test_service):
        """Тест закрытия ресурсов сервиса"""
        # Проверяем, что клиент существует
        assert test_service.client is not None
        
        # Закрываем сервис
        await test_service.close()
        
        # Проверяем, что клиент закрыт (не можем напрямую проверить,
        # но убедимся, что метод не вызывает исключений)
        assert True