import pytest
from unittest.mock import AsyncMock, patch
from services import call_decomposer, call_integrator, background_processing
import repositories as repo


@pytest.mark.asyncio
async def test_call_decomposer_success(mocker):
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mock_post.json = AsyncMock(return_value={"patches": ["IMP-001"]})
    mocker.patch("services.client.post", return_value=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == ["IMP-001"]


@pytest.mark.asyncio
async def test_call_decomposer_http_error(mocker):
    mock_post = AsyncMock()
    mock_post.raise_for_status.side_effect = Exception("HTTP Error")
    mocker.patch("services.client.post", return_value=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == []


@pytest.mark.asyncio
async def test_call_decomposer_empty_patches(mocker):
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mock_post.json = AsyncMock(return_value={"patches": []})
    mocker.patch("services.client.post", return_value=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == []


@pytest.mark.asyncio
async def test_call_integrator_success(mocker):
    mock_post = AsyncMock()
    mock_post.return_value.status_code = 200
    mocker.patch("services.client.post", return_value=mock_post)
    await call_integrator(["IMP-001"], "task_id")
    mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_call_integrator_error(mocker):
    mock_post = AsyncMock()
    mock_post.raise_for_status.side_effect = Exception("Error")
    mocker.patch("services.client.post", return_value=mock_post)
    await call_integrator(["IMP-001"], "task_id")  # should not raise


@pytest.mark.asyncio
async def test_background_processing_success(mocker):
    mocker.patch("services.call_decomposer", return_value=["IMP-001"])
    mocker.patch("services.call_integrator", return_value=None)
    mocker.patch("services.repo.update_task_status", return_value=None)
    await background_processing("proj_123", {"description": "test"}, "task_id")
    repo.update_task_status.assert_called_with("task_id", "IN_PROGRESS", "Decomposed into 1 patches")


@pytest.mark.asyncio
async def test_background_processing_empty_patches(mocker):
    mocker.patch("services.call_decomposer", return_value=[])
    mocker.patch("services.call_integrator", return_value=None)
    mocker.patch("services.repo.update_task_status", return_value=None)
    await background_processing("proj_123", {"description": "test"}, "task_id")
    repo.update_task_status.assert_called_with("task_id", "NEW", "Decomposition returned no patches")