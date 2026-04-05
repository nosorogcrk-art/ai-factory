import pytest
from unittest.mock import patch, AsyncMock
from services import fetch_json, read_tasks, aggregate_status

@pytest.mark.asyncio
async def test_fetch_json_success():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_resp = AsyncMock()
        mock_resp.json = lambda: {"data": "test"}  # синхронный метод
        mock_resp.raise_for_status = AsyncMock()
        mock_get.return_value = mock_resp
        result = await fetch_json("http://example.com")
        assert result == {"data": "test"}

@pytest.mark.asyncio
async def test_fetch_json_error():
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_get.side_effect = Exception("Network error")
        result = await fetch_json("http://example.com", default={"default": True})
        assert result == {"default": True}

def test_read_tasks(tmp_path):
    import json
    test_file = tmp_path / "tasks.json"
    test_file.write_text(json.dumps([{"id": "1"}]))
    tasks = read_tasks(str(test_file))
    assert tasks == [{"id": "1"}]

def test_read_tasks_not_found():
    tasks = read_tasks("/nonexistent/path.json")
    assert tasks == []

@pytest.mark.asyncio
async def test_aggregate_status():
    with patch("services.fetch_json") as mock_fetch, patch("services.read_tasks") as mock_read:
        mock_fetch.side_effect = [
            {"branches": [{"id": "BR1"}]},
            {"metrics": {"cpu": 10}},
            {"total": 5, "active": 3}
        ]
        mock_read.return_value = [{"id": "task1"}]
        result = await aggregate_status("http://reg", "http://metrics", "http://skills", "/path")
        assert result.branches == [{"id": "BR1"}]
        assert result.metrics == {"metrics": {"cpu": 10}}
        assert result.skill_stats == {"total": 5, "active": 3}
        assert result.tasks == [{"id": "task1"}]