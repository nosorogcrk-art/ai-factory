import pytest
from unittest.mock import AsyncMock, patch
from argus_watcher import watch_projects, load_processed, save_processed

@pytest.mark.asyncio
async def test_watcher_creates_task_for_new_project():
    with patch("argus_watcher.get_projects", AsyncMock(return_value=[{"id": "new123", "name": "Test"}])), \
         patch("argus_watcher.create_task", AsyncMock()) as mock_create, \
         patch("argus_watcher.load_processed", return_value=set()), \
         patch("argus_watcher.save_processed") as mock_save:
        await watch_projects()  # one iteration only
        mock_create.assert_called_once_with("new123", "Test")
        mock_save.assert_called_once()

@pytest.mark.asyncio
async def test_watcher_ignores_processed():
    with patch("argus_watcher.get_projects", AsyncMock(return_value=[{"id": "old123", "name": "Old"}])), \
         patch("argus_watcher.create_task", AsyncMock()) as mock_create, \
         patch("argus_watcher.load_processed", return_value={"old123"}):
        await watch_projects()
        mock_create.assert_not_called()

def test_load_save_processed(tmp_path):
    test_file = tmp_path / "processed.json"
    with patch("argus_watcher.PROCESSED_FILE", str(test_file)):
        save_processed({"a", "b"})
        loaded = load_processed()
        assert loaded == {"a", "b"}


@pytest.mark.asyncio
async def test_start_dialogue_calls_cognitive_engine():
    with patch("aiohttp.ClientSession.post", AsyncMock()) as mock_post:
        from argus_watcher import start_dialogue
        await start_dialogue("proj_123", "Test project")
        # Проверить, что был вызван POST /generate_hints
        mock_post.assert_called()
