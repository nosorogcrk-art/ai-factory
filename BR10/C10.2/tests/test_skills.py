import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from services import check_skills_real

@pytest.mark.asyncio
async def test_check_skills_real_all_passed():
    responses = [
        MagicMock(status_code=200, json=MagicMock(return_value={"passed": True, "output": "ok", "duration_seconds": 0.1})),
        MagicMock(status_code=200, json=MagicMock(return_value={"passed": True, "output": "ok", "duration_seconds": 0.2}))
    ]
    async def mock_post(*args, **kwargs):
        return responses.pop(0)
    with patch("httpx.AsyncClient.post", new=mock_post):
        all_passed, results = await check_skills_real(["SKILL-001", "SKILL-002"], "job123")
        assert all_passed is True
        assert len(results) == 2
        assert results[0]["passed"] is True
        assert results[1]["passed"] is True

@pytest.mark.asyncio
async def test_check_skills_real_one_failed():
    responses = [
        MagicMock(status_code=200, json=MagicMock(return_value={"passed": True, "output": "ok", "duration_seconds": 0.1})),
        MagicMock(status_code=200, json=MagicMock(return_value={"passed": False, "output": "error", "duration_seconds": 0.2}))
    ]
    async def mock_post(*args, **kwargs):
        return responses.pop(0)
    with patch("httpx.AsyncClient.post", new=mock_post):
        all_passed, results = await check_skills_real(["SKILL-001", "SKILL-002"], "job123")
        assert all_passed is False
        assert results[0]["passed"] is True
        assert results[1]["passed"] is False

@pytest.mark.asyncio
async def test_check_skills_real_http_error():
    async def mock_post(*args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal error"
        return mock_resp
    with patch("httpx.AsyncClient.post", new=mock_post):
        all_passed, results = await check_skills_real(["SKILL-001"], "job123")
        assert all_passed is False
        assert results[0]["passed"] is False
        assert "HTTP 500" in results[0]["output"]

@pytest.mark.asyncio
async def test_check_skills_real_connection_error():
    async def mock_post(*args, **kwargs):
        raise Exception("Connection refused")
    with patch("httpx.AsyncClient.post", new=mock_post):
        all_passed, results = await check_skills_real(["SKILL-001"], "job123")
        assert all_passed is False
        assert results[0]["passed"] is False
        assert "Connection refused" in results[0]["output"]

@pytest.mark.asyncio
async def test_check_skills_real_empty_list():
    all_passed, results = await check_skills_real([], "job123")
    assert all_passed is True
    assert results == []