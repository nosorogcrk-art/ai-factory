import sys
from pathlib import Path

# Добавляем путь к папке контейнера C10.1, чтобы импортировать main и services
sys.path.insert(0, str(Path(__file__).parent.parent))

from services import build_patches


def test_build_patches_success(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=True)
    mocker.patch("services.repositories.update_task_status", return_value=True)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is True
    assert "Build started" in msg


def test_build_patches_apply_fails(mocker):
    mocker.patch("services._apply_patches", return_value=False)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is False
    assert "Failed to apply patches" in msg


def test_build_patches_build_fails(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=False)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is False
    assert "Build failed" in msg


def test_build_patches_without_task_id(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=True)
    success, msg = build_patches(None, ["IMP-001"], check_skills=True, run_tests=True)
    assert success is True
    assert "Build started" in msg


import pytest
from unittest.mock import AsyncMock, patch
from services import generate_code_from_l5


@pytest.mark.asyncio
async def test_generate_code_from_l5_success():
    # Создаем мок ответа с асинхронным методом json()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    # Имитируем ответ C7.4
    mock_response.json = AsyncMock(return_value={
        "result": {
            "files": [{"path": "main.py", "content": "print('hello')"}]
        },
        "skill_id": "SKILL-CODE-GEN-001",
        "warnings": []
    })
    
    # httpx.AsyncClient.post возвращает корутину, которая возвращает ответ
    async def mock_post(*args, **kwargs):
        return mock_response
    
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        files = await generate_code_from_l5("test", {"key": "value"})
        assert len(files) == 1
        assert files[0]["path"] == "main.py"
        assert files[0]["content"] == "print('hello')"


@pytest.mark.asyncio
async def test_generate_code_from_l5_http_error():
    with patch("httpx.AsyncClient.post", side_effect=Exception("Network error")):
        with pytest.raises(Exception, match="Failed to generate code"):
            await generate_code_from_l5("test", {})


@pytest.mark.asyncio
async def test_generate_code_from_l5_no_files():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={
        "result": {
            "error": "No files generated"
        },
        "skill_id": "SKILL-CODE-GEN-001",
        "warnings": []
    })
    
    async def mock_post(*args, **kwargs):
        return mock_response
    
    with patch("httpx.AsyncClient.post", side_effect=mock_post):
        with pytest.raises(Exception, match="Failed to generate code: No files generated"):
            await generate_code_from_l5("test", {"key": "value"})
