import pytest
from unittest.mock import AsyncMock
from services import call_decomposer, call_integrator, background_processing, process_dialog
import repositories as repo


@pytest.mark.asyncio
async def test_call_decomposer_success(mocker):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={"patches": ["IMP-001"]})
    mock_response.raise_for_status = AsyncMock()
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == ["IMP-001"]


@pytest.mark.asyncio
async def test_call_decomposer_http_error(mocker):
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP Error")
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == []


@pytest.mark.asyncio
async def test_call_decomposer_empty_patches(mocker):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = AsyncMock(return_value={"patches": []})
    mock_response.raise_for_status = AsyncMock()
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    patches = await call_decomposer("description", "task_id")
    assert patches == []


@pytest.mark.asyncio
async def test_call_integrator_success(mocker):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = AsyncMock()
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    await call_integrator(["IMP-001"], "task_id")
    mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_call_integrator_error(mocker):
    mock_response = AsyncMock()
    mock_response.raise_for_status.side_effect = Exception("Error")
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
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


@pytest.mark.asyncio
async def test_process_dialog_without_deepseek_key(mocker):
    """Test process_dialog when DEEPSEEK_API_KEY is not set"""
    # Mock repository functions
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = ([], {})
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_response)
    
    # Mock os.getenv to return None for DEEPSEEK_API_KEY
    mocker.patch("services.os.getenv", side_effect=lambda key, default=None: None if key == "DEEPSEEK_API_KEY" else default)
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Hello")
    
    # Verify fallback response
    assert "Привет! Я помогу вам сформулировать задачу" in reply
    assert completed is False
    assert task_id is None
    assert task_description is None


@pytest.mark.asyncio
async def test_process_dialog_with_deepseek_key_success(mocker):
    """Test process_dialog when DEEPSEEK_API_KEY is set and API call succeeds"""
    # Mock repository functions
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = ([], {})
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Mock DEEPSEEK_API_KEY
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    
    # Mock successful API response
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {
        "choices": [{"message": {"content": '{"title": "Test", "description": "Test", "requirements": [], "technical_specs": {}, "deliverable": "code", "priority": "medium", "tags": []}'}}]
    }
    mocker.patch("services.client.post", return_value=mock_post_response)
    
    # Mock task creation
    mock_create_task = mocker.patch("services.create_task_in_registry")
    mock_create_task.return_value = "DIALOG-123"
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Create a test app")
    
    # Verify response
    assert "✅ Задача сформирована!" in reply
    assert completed is True
    assert task_id == "DIALOG-123"
    assert task_description is not None


@pytest.mark.asyncio
async def test_process_dialog_with_deepseek_key_error(mocker):
    """Test process_dialog when DEEPSEEK_API_KEY is set but API call fails"""
    # Mock repository functions
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = ([], {})
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Mock DEEPSEEK_API_KEY
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    
    # Mock failed API response
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.side_effect = Exception("API Error")
    mocker.patch("services.client.post", return_value=mock_post_response)
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Create a test app")
    
    # Verify fallback response for API error
    assert "Извините, сервис временно недоступен" in reply
    assert completed is False
    assert task_id is None
    assert task_description is None


# Новые тесты для P9.4.1 - интеграция с C7.4 Skill Integrator
@pytest.mark.asyncio
async def test_call_skill_integrator_success(mocker):
    """Test successful call to C7.4 skill integrator"""
    from services import call_skill_integrator
    
    # Mock successful response
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "skill_id": "discovery_v1",
        "prompt": "Ты — ассистент для опроса пользователя. Задавай вопросы...",
        "version": "1.0"
    }
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    
    # Mock logging
    mocker.patch("services.send_log_to_br18")
    
    result = await call_skill_integrator("discovery")
    
    assert result is not None
    assert result["skill_id"] == "discovery_v1"
    assert "prompt" in result
    mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_call_skill_integrator_timeout(mocker):
    """Test timeout when calling C7.4 skill integrator"""
    from services import call_skill_integrator
    
    # Mock timeout
    mock_post = AsyncMock(side_effect=Exception("Timeout"))
    mocker.patch("services.client.post", new=mock_post)
    
    # Mock logging
    mocker.patch("services.send_log_to_br18")
    
    result = await call_skill_integrator("discovery")
    
    assert result is None


@pytest.mark.asyncio
async def test_call_skill_integrator_invalid_response(mocker):
    """Test invalid response structure from C7.4"""
    from services import call_skill_integrator
    
    # Mock response without prompt field
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"skill_id": "discovery_v1"}  # missing prompt
    mock_post = AsyncMock(return_value=mock_response)
    mocker.patch("services.client.post", new=mock_post)
    
    # Mock logging
    mocker.patch("services.send_log_to_br18")
    
    result = await call_skill_integrator("discovery")
    
    assert result is None


@pytest.mark.asyncio
async def test_process_dialog_new_project_with_skill_success(mocker):
    """Test process_dialog for new project with successful skill loading"""
    # Mock repository functions - empty history for new project
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = ([], {})
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Mock successful skill integrator call
    mock_skill_response = {"skill_id": "discovery_v1", "prompt": "Custom skill prompt for discovery"}
    mocker.patch("services.call_skill_integrator", return_value=mock_skill_response)
    
    # Mock DEEPSEEK_API_KEY and API call
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {
        "choices": [{"message": {"content": "I'll help you with your project. What problem do you want to solve?"}}]
    }
    mocker.patch("services.client.post", return_value=mock_post_response)
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Hello")
    
    # Verify skill integrator was called
    from services import call_skill_integrator
    call_skill_integrator.assert_called_once_with("discovery")
    
    # Verify response
    assert completed is False
    assert task_id is None


@pytest.mark.asyncio
async def test_process_dialog_new_project_skill_fallback(mocker):
    """Test process_dialog for new project with skill integrator failure (fallback)"""
    # Mock repository functions - empty history for new project
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = ([], {})
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists
    mock_get_response = AsyncMock()
    mock_get_response.status_code = 200
    mock_get_response.raise_for_status.return_value = None
    mocker.patch("services.client.get", return_value=mock_get_response)
    
    # Mock failed skill integrator call
    mocker.patch("services.call_skill_integrator", return_value=None)
    
    # Mock DEEPSEEK_API_KEY and API call
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {
        "choices": [{"message": {"content": "I'll help you with your project. What problem do you want to solve?"}}]
    }
    mocker.patch("services.client.post", return_value=mock_post_response)
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Hello")
    
    # Verify skill integrator was called
    from services import call_skill_integrator
    call_skill_integrator.assert_called_once_with("discovery")
    
    # Verify fallback was used
    assert completed is False
    assert task_id is None


@pytest.mark.asyncio
async def test_process_dialog_existing_project_uses_saved_prompt(mocker):
    """Test process_dialog for existing project uses saved system prompt"""
    # Mock repository functions - existing history and collected data with saved prompt
    mock_get_session = mocker.patch("services.repo.get_session")
    mock_get_session.return_value = (
        [{"role": "user", "content": "Previous message"}, {"role": "assistant", "content": "Previous reply"}],
        {"system_prompt": "Saved custom prompt", "skill_id": "discovery_v1"}
    )
    mocker.patch("services.repo.save_session")
    
    # Mock external service calls
    mocker.patch("services.send_log_to_br18")
    mocker.patch("services.save_message_to_project")
    
    # Mock project verification - project exists (skip because history exists)
    
    # Mock DEEPSEEK_API_KEY and API call
    mocker.patch("services.DEEPSEEK_API_KEY", "test-key")
    mock_post_response = AsyncMock()
    mock_post_response.raise_for_status.return_value = None
    mock_post_response.json.return_value = {
        "choices": [{"message": {"content": "Continuing the conversation..."}}]
    }
    mocker.patch("services.client.post", return_value=mock_post_response)
    
    # Call process_dialog
    reply, completed, task_id, task_description = await process_dialog("proj_123", "Next message")
    
    # Verify skill integrator was NOT called (existing project)
    from services import call_skill_integrator
    call_skill_integrator.assert_not_called()
    
    # Verify response
    assert completed is False
    assert task_id is None


def test_load_hints(tmp_path):
    from services import load_hints
    hints_dir = tmp_path / "ПОДСКАЗКИ"
    hints_dir.mkdir()
    hints_file = hints_dir / "proj_123_hints.json"
    hints_file.write_text('{"hints": [{"project_id": "proj_1"}]}')
    with patch("services.HINTS_DIR", hints_dir):
        result = load_hints("proj_123")
        assert result["hints"][0]["project_id"] == "proj_1"
