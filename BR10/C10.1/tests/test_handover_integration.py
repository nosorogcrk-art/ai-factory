import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app
import services

client = TestClient(app)

def test_build_with_patch_ids_returns_files():
    response = client.post("/build", json={"task_id": "test", "patch_ids": ["P1"]})
    assert response.status_code == 200
    data = response.json()
    assert "files" in data
    assert len(data["files"]) == 5  # main.py, models.py, database.py, requirements.txt, templates/index.html
    filenames = [f["filename"] for f in data["files"]]
    assert "main.py" in filenames
    assert "models.py" in filenames
    assert "database.py" in filenames
    assert "requirements.txt" in filenames
    assert "templates/index.html" in filenames

def test_build_with_empty_patch_ids_returns_400():
    response = client.post("/build", json={"task_id": "test", "patch_ids": []})
    assert response.status_code == 400

def test_build_without_task_id_returns_422():
    response = client.post("/build", json={"patch_ids": ["P1"]})
    assert response.status_code == 422  # Pydantic validation error

def test_build_without_patch_ids_returns_422():
    response = client.post("/build", json={"task_id": "test"})
    assert response.status_code == 422  # Pydantic validation error

@pytest.mark.asyncio
async def test_generate_code_from_patches_returns_fallback():
    """
    Тест проверяет, что функция всегда возвращает fallback TODO-приложение
    (временно отключен вызов навыка из-за ошибки 502).
    """
    files = await services.generate_code_from_patches("test", ["P1"])
    # Проверяем, что возвращаются файлы TODO-приложения
    assert len(files) == 5  # main.py, models.py, database.py, requirements.txt, templates/index.html
    filenames = [f["filename"] for f in files]
    assert "main.py" in filenames
    assert "models.py" in filenames
    assert "database.py" in filenames
    assert "requirements.txt" in filenames
    assert "templates/index.html" in filenames
    # Проверяем содержание main.py
    main_py = next(f for f in files if f["filename"] == "main.py")
    assert "TODO App" in main_py["content"]
    assert "sqlalchemy" in main_py["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_fallback_when_no_patches():
    with patch("services.fetch_patches_details", return_value=[]):
        files = await services.generate_code_from_patches("test", ["P1"])
        # Теперь fallback возвращает несколько файлов TODO-приложения
        assert len(files) >= 5  # main.py, models.py, database.py, requirements.txt, templates/index.html
        filenames = [f["filename"] for f in files]
        assert "main.py" in filenames
        # Проверяем, что это TODO-приложение
        main_py = next(f for f in files if f["filename"] == "main.py")
        assert "TODO App" in main_py["content"]
        assert "sqlalchemy" in main_py["content"]

@pytest.mark.asyncio
async def test_generate_code_from_patches_fallback_when_skill_fails():
    with patch("services.fetch_patches_details", return_value=[{"id": "P1", "title": "Test"}]):
        with patch("httpx.AsyncClient.post", side_effect=Exception("Connection error")):
            files = await services.generate_code_from_patches("test", ["P1"])
            # Теперь fallback возвращает несколько файлов TODO-приложения
            assert len(files) >= 5  # main.py, models.py, database.py, requirements.txt, templates/index.html
            filenames = [f["filename"] for f in files]
            assert "main.py" in filenames
            assert "models.py" in filenames
            assert "database.py" in filenames
            assert "requirements.txt" in filenames
            # Проверяем, что это TODO-приложение
            main_py = next(f for f in files if f["filename"] == "main.py")
            assert "TODO App" in main_py["content"]
            assert "sqlalchemy" in main_py["content"]
