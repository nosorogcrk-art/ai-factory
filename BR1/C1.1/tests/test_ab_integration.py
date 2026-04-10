"""
Тесты для интеграции A/B тестирования с C19.4.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
import sys
import os

# Добавляем путь к модулю
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app
from services import get_ab_version, send_ab_metric


class TestABIntegration:
    """Тесты для функций A/B тестирования."""
    
    @pytest.mark.asyncio
    async def test_get_ab_version_success(self):
        """Тест успешного получения версии от C19.4."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"version": "v1.2.3"}
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            version = await get_ab_version("prompt", "discovery", "test_context")
            assert version == "v1.2.3"
    
    @pytest.mark.asyncio
    async def test_get_ab_version_failure(self):
        """Тест неудачного получения версии (C19.4 недоступен)."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.side_effect = Exception("Connection error")
            mock_client_class.return_value = mock_client
            
            version = await get_ab_version("prompt", "discovery")
            assert version is None
    
    @pytest.mark.asyncio
    async def test_get_ab_version_no_experiment(self):
        """Тест получения версии, когда эксперимента нет (404)."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 404
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            version = await get_ab_version("skill", "branch_design")
            assert version is None
    
    @pytest.mark.asyncio
    async def test_send_ab_metric_success(self):
        """Тест успешной отправки метрики в C19.4."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_response = MagicMock()
            mock_response.status_code = 200
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.return_value = mock_response
            mock_client_class.return_value = mock_client
            
            # Не должно быть исключений
            await send_ab_metric(
                experiment_id="exp_123",
                variant="v1.0",
                success=True,
                duration_ms=1500,
                cost_usd=0.05,
                context="test_context"
            )
    
    @pytest.mark.asyncio
    async def test_send_ab_metric_failure(self):
        """Тест неудачной отправки метрики (C19.4 недоступен)."""
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.post.side_effect = Exception("Connection error")
            mock_client_class.return_value = mock_client
            
            # Не должно быть исключений, только логирование
            await send_ab_metric(
                experiment_id="exp_123",
                variant="v1.0",
                success=False,
                duration_ms=2000
            )


class TestABEndpoints:
    """Тесты для эндпоинтов A/B тестирования."""
    
    def setup_method(self):
        self.client = TestClient(app)
    
    @pytest.mark.asyncio
    async def test_ab_version_endpoint_success(self):
        """Тест эндпоинта /api/ab/version с успешным ответом."""
        with patch('main.get_ab_version', new_callable=AsyncMock) as mock_get_version:
            mock_get_version.return_value = "v2.1.0"
            
            response = self.client.get("/api/ab/version/prompt/discovery?context=test")
            assert response.status_code == 200
            data = response.json()
            assert data["version"] == "v2.1.0"
    
    @pytest.mark.asyncio
    async def test_ab_version_endpoint_no_version(self):
        """Тест эндпоинта /api/ab/version, когда версии нет."""
        with patch('main.get_ab_version', new_callable=AsyncMock) as mock_get_version:
            mock_get_version.return_value = None
            
            response = self.client.get("/api/ab/version/skill/branch_design")
            assert response.status_code == 200
            data = response.json()
            assert data["version"] is None
    
    @pytest.mark.asyncio
    async def test_ab_metric_endpoint(self):
        """Тест эндпоинта /api/ab/metrics."""
        with patch('main.send_ab_metric', new_callable=AsyncMock) as mock_send_metric:
            mock_send_metric.return_value = None
            
            payload = {
                "experiment_id": "exp_456",
                "variant": "v1.5",
                "success": True,
                "duration_ms": 1200,
                "cost_usd": 0.03,
                "context": "integration_test"
            }
            
            response = self.client.post("/api/ab/metrics", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"
    
    @pytest.mark.asyncio
    async def test_ab_metric_endpoint_minimal_payload(self):
        """Тест эндпоинта /api/ab/metrics с минимальным payload."""
        with patch('main.send_ab_metric', new_callable=AsyncMock) as mock_send_metric:
            mock_send_metric.return_value = None
            
            payload = {
                "experiment_id": "exp_789",
                "variant": "v2.0",
                "success": False,
                "duration_ms": 500
            }
            
            response = self.client.post("/api/ab/metrics", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "accepted"


class TestABIntegrationWithC19:
    """Интеграционные тесты с моком C19.4."""
    
    @pytest.mark.asyncio
    async def test_full_flow_prompt_version(self):
        """Полный тест потока: запрос версии -> отправка метрики."""
        # Мокаем оба вызова
        with patch('httpx.AsyncClient') as mock_client_class:
            # Настройка мока для первого вызова (получение версии)
            mock_version_response = MagicMock()
            mock_version_response.status_code = 200
            mock_version_response.json.return_value = {"version": "experimental_v1"}
            
            # Настройка мока для второго вызова (отправка метрики)
            mock_metric_response = MagicMock()
            mock_metric_response.status_code = 200
            
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            
            # Настраиваем side_effect для последовательных вызовов
            mock_client.get.return_value = mock_version_response
            mock_client.post.return_value = mock_metric_response
            mock_client_class.return_value = mock_client
            
            # Получаем версию
            version = await get_ab_version("prompt", "discovery")
            assert version == "experimental_v1"
            
            # Отправляем метрику
            await send_ab_metric(
                experiment_id="prompt_discovery",
                variant="experimental_v1",
                success=True,
                duration_ms=800
            )
            
            # Проверяем, что были вызваны оба метода
            assert mock_client.get.call_count == 1
            assert mock_client.post.call_count == 1
    
    @pytest.mark.asyncio
    async def test_background_tasks_integration(self):
        """Тест интеграции с BackgroundTasks."""
        from fastapi import BackgroundTasks
        from fastapi.testclient import TestClient
        from main import app
        
        with patch('main.send_ab_metric', new_callable=AsyncMock) as mock_send_metric:
            mock_send_metric.return_value = None
            
            # Создаем клиент и вызываем эндпоинт с BackgroundTasks
            client = TestClient(app)
            
            payload = {
                "experiment_id": "test_exp",
                "variant": "v1.0",
                "success": True,
                "duration_ms": 1000,
                "cost_usd": 0.01,
                "context": "test"
            }
            
            response = client.post("/api/ab/metrics", json=payload)
            assert response.status_code == 200
            
            # Даём время на выполнение фоновой задачи
            await asyncio.sleep(0.1)
            
            # Проверяем, что функция была вызвана
            assert mock_send_metric.called
            assert mock_send_metric.call_count == 1
            
            # Проверяем аргументы вызова
            mock_send_metric.assert_called_with(
                "test_exp",
                "v1.0",
                True,
                1000,
                0.01,
                "test"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])