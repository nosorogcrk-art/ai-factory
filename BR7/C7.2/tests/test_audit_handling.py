import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, mock_open, Mock
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_run_code_audit_success():
    # Создаем мок ответа
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"passed": True, "issues": [], "suggestions": []}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        from api import run_code_audit
        result = await run_code_audit([{"path": "test.py", "content": "print(1)"}])
        assert result["passed"] is True

@pytest.mark.asyncio
async def test_package_build_result_success():
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "success", "artifact_url": "/test.zip"}
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        from api import package_build_result
        result = await package_build_result([{"path": "test.py", "content": "print(1)"}])
        assert result["status"] == "success"

@pytest.mark.asyncio
async def test_create_rework_task():
    mock_response = Mock()
    mock_response.status_code = 200
    
    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_response
        from api import create_rework_task
        await create_rework_task("proj1", ["no tests"], ["add tests"])
        mock_post.assert_awaited()

@pytest.mark.asyncio
async def test_check_and_build_queue_with_audit_passed():
    # Мокируем существование файла очереди, но не обработанного флага
    def exists_side_effect(self):
        # self - объект Path
        path_str = str(self)
        # Если путь заканчивается на .processed, возвращаем False
        if path_str.endswith(".processed"):
            return False
        # Иначе True (для queue_file)
        return True
    
    with patch.object(Path, 'exists', side_effect=exists_side_effect, autospec=True), \
         patch.object(Path, 'touch', side_effect=lambda *args, **kwargs: None), \
         patch("builtins.open", mock_open(read_data='[{"container_id": "c1", "spec": {}}]')), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        # Первый вызов (build_from_queue) – успех с файлами
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"status": "success", "files": [{"path": "main.py", "content": "print(1)"}]}]
        }
        mock_post.return_value = mock_response
        # Второй вызов (run_code_audit) – passed
        # Третий вызов (package_build_result) – успех
        # У нас только один mock_post, он будет возвращать разные результаты при последовательных вызовах
        # Для упрощения: подменим функцию audit и package отдельно
        with patch("api.run_code_audit", new_callable=AsyncMock, return_value={"passed": True}), \
             patch("api.package_build_result", new_callable=AsyncMock, return_value={"status": "success"}):
            from api import check_and_build_queue
            result = await check_and_build_queue()
            # Должен быть success, потому что очередь есть и не обработана
            assert result.get("status") == "success"
            assert result.get("audit_processed") is True

@pytest.mark.asyncio
async def test_check_and_build_queue_with_audit_failed():
    # Мокируем существование файла очереди, но не обработанного флага
    def exists_side_effect(self):
        # self - объект Path
        path_str = str(self)
        if path_str.endswith(".processed"):
            return False
        return True
    
    with patch.object(Path, 'exists', side_effect=exists_side_effect, autospec=True), \
         patch.object(Path, 'touch', side_effect=lambda *args, **kwargs: None), \
         patch("builtins.open", mock_open(read_data='[{"container_id": "c1", "spec": {}}]')), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [{"status": "success", "files": [{"path": "main.py", "content": "print(1)"}]}]
        }
        mock_post.return_value = mock_response
        with patch("api.run_code_audit", new_callable=AsyncMock) as mock_audit, \
             patch("api.create_rework_task", new_callable=AsyncMock) as mock_task:
            mock_audit.return_value = {"passed": False, "issues": ["bad"], "suggestions": ["fix"]}
            mock_task.return_value = None
            from api import check_and_build_queue
            result = await check_and_build_queue()
            # Должна быть создана задача, аудит обработан
            assert mock_audit.called is True
            assert mock_task.called is True
            assert result.get("audit_processed") is True

def test_trigger_build_endpoint():
    with patch("api.check_and_build_queue", new_callable=AsyncMock, return_value={"status": "success", "message": "Build triggered", "audit_processed": True}):
        response = client.post("/trigger_build")
        assert response.status_code == 200
        assert response.json()["status"] == "success"