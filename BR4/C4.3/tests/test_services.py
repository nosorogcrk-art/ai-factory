import pytest
from unittest.mock import AsyncMock, patch
import httpx
from services import parse_command, call_handover

def test_parse_command():
    assert parse_command("take 123") == {"cmd": "take", "args": ["123"]}
    assert parse_command("  complete  task-1  ") == {"cmd": "complete", "args": ["task-1"]}
    assert parse_command("") == {"cmd": "", "args": []}

@pytest.mark.asyncio
async def test_call_handover_success():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        mock_resp.json = lambda: {"status": "ok"}
        mock_post.return_value = mock_resp
        result = await call_handover("POST", "/take", {"task_id": "123"})
        assert result == {"status": "ok"}

@pytest.mark.asyncio
async def test_call_handover_http_error():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_resp = AsyncMock()
        mock_resp.status_code = 404
        mock_resp.json = lambda: {"detail": "Not found"}
        error = httpx.HTTPStatusError(
            "404 Client Error: Not Found",
            request=AsyncMock(),
            response=mock_resp
        )
        mock_resp.raise_for_status.side_effect = error
        mock_post.return_value = mock_resp

        result = await call_handover("POST", "/take", {"task_id": "123"})
        # Проверяем, что в ответе есть поле 'detail' (так как сервис возвращает ошибку с полем 'detail')
        assert "detail" in result
        assert result["detail"] == "Not found"