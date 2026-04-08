import pytest
import sys
import os
from unittest.mock import AsyncMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services import decompose_task, call_container_design


@pytest.mark.asyncio
async def test_decompose_task_success():
    l2_json = '{"title": "Test", "description": "Test", "requirements": []}'
    context = {"project_id": "test"}
    with patch("services.call_skill_integrator", AsyncMock(return_value="skill prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value='{"branches": [{"id": "BR-TEST-1", "name": "Test", "description": "desc", "containers": []}]}')), \
         patch("services.save_branch_passport", AsyncMock()), \
         patch("services.call_container_design", AsyncMock(return_value=None)), \
         patch("services.save_container_passport", AsyncMock()):
        result = await decompose_task(l2_json, context)
        assert "branches" in result
        assert len(result["branches"]) == 1
        assert result["branches"][0]["id"] == "BR-TEST-1"
        assert result["patches"] == ["BR-TEST-1"]


@pytest.mark.asyncio
async def test_call_container_design_success():
    with patch("services.call_skill_integrator", AsyncMock(return_value="some prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value='{"branches": [{"branch_id": "BR-TEST-1", "containers": [{"id": "C-TEST-1.1", "name": "Test", "description": "desc", "port": 8080}]}]}')):
        result = await call_container_design({"title": "Test"}, [])
        assert result is not None
        assert "branches" in result
        assert len(result["branches"]) == 1
        assert result["branches"][0]["branch_id"] == "BR-TEST-1"
        assert len(result["branches"][0]["containers"]) == 1
        assert result["branches"][0]["containers"][0]["id"] == "C-TEST-1.1"


@pytest.mark.asyncio
async def test_decompose_task_invalid_json():
    result = await decompose_task("invalid json", {})
    assert result == {"patches": [], "branches": []}


@pytest.mark.asyncio
async def test_decompose_task_missing_fields():
    l2_json = '{"title": "Test"}'
    result = await decompose_task(l2_json, {})
    assert result == {"patches": [], "branches": []}


@pytest.mark.asyncio
async def test_decompose_task_no_skill_prompt():
    l2_json = '{"title": "Test", "description": "Test", "requirements": []}'
    with patch("services.call_skill_integrator", AsyncMock(return_value=None)):
        result = await decompose_task(l2_json, {})
        assert result == {"patches": [], "branches": []}


@pytest.mark.asyncio
async def test_decompose_task_deepseek_failure():
    l2_json = '{"title": "Test", "description": "Test", "requirements": []}'
    with patch("services.call_skill_integrator", AsyncMock(return_value="skill prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value=None)):
        result = await decompose_task(l2_json, {})
        assert result == {"patches": [], "branches": []}


@pytest.mark.asyncio
async def test_decompose_task_invalid_branches_json():
    l2_json = '{"title": "Test", "description": "Test", "requirements": []}'
    with patch("services.call_skill_integrator", AsyncMock(return_value="skill prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value="invalid json")):
        result = await decompose_task(l2_json, {})
        assert result == {"patches": [], "branches": []}


@pytest.mark.asyncio
async def test_call_patch_design_success():
    """Успешный сценарий: DeepSeek возвращает валидный JSON с патчами."""
    with patch("services.call_skill_integrator", AsyncMock(return_value="some prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value='{"patches": [{"id": "P-TEST-1", "title": "Test", "description": "desc", "dependencies": [], "required_skills": []}]}')):
        from services import call_patch_design
        result = await call_patch_design({"title": "Test"}, [], [])
        assert result is not None
        assert "patches" in result
        assert len(result["patches"]) == 1


@pytest.mark.asyncio
async def test_call_patch_design_failure():
    """Сценарий ошибки: навык не получен (C7.4 вернул None)."""
    with patch("services.call_skill_integrator", AsyncMock(return_value=None)):
        from services import call_patch_design
        result = await call_patch_design({"title": "Test"}, [], [])
        assert result is None


@pytest.mark.asyncio
async def test_call_patch_design_invalid_json():
    """Сценарий ошибки: DeepSeek возвращает невалидный JSON."""
    with patch("services.call_skill_integrator", AsyncMock(return_value="some prompt")), \
         patch("services.call_deepseek", AsyncMock(return_value="not a json")):
        from services import call_patch_design
        result = await call_patch_design({"title": "Test"}, [], [])
        assert result is None
