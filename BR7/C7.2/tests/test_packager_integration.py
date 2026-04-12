import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, Mock
from services import call_packager

@pytest.mark.asyncio
async def test_call_packager_success():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    # httpx.Response.json() - синхронный метод, не требует await
    mock_response.json = Mock(return_value={"status": "ok", "archive_path": "/path/to/archive.zip"})
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await call_packager("test_proj", [{"filename": "a.txt", "content": "test"}])
        assert result == "/path/to/archive.zip"

@pytest.mark.asyncio
async def test_call_packager_with_path():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = Mock(return_value={"status": "ok", "archive_path": "/path/to/archive.zip"})
    with patch("httpx.AsyncClient.post", return_value=mock_response):
        result = await call_packager("test_proj", [{"path": "dir/a.txt", "content": "test"}])
        assert result == "/path/to/archive.zip"

@pytest.mark.asyncio
async def test_call_packager_http_error():
    with patch("httpx.AsyncClient.post", side_effect=Exception("Connection refused")):
        with pytest.raises(Exception):
            await call_packager("test_proj", [])

@pytest.mark.asyncio
async def test_call_packager_invalid_file_format():
    with pytest.raises(ValueError):
        await call_packager("test_proj", [{"invalid": "key"}])
