import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch
import json
from services import call_skill, decompose_l2


@pytest.mark.asyncio
async def test_call_skill_success():
    from unittest.mock import Mock
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": {"test": "ok"}}
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        result = await call_skill("test", {})
        assert result == {"test": "ok"}


@pytest.mark.asyncio
async def test_decompose_l2_full_chain():
    with patch("services.call_skill", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = [
            {"branches": [{"id": "BR1", "name": "Branch 1", "description": "Desc", "containers": []}]},
            {"containers": [{"id": "C1", "name": "Container 1", "description": "Desc"}]},
            {"patches": [{"id": "P1", "title": "Patch 1", "description": "Desc"}]},
            {"queue": ["P1"]}
        ]
        result = await decompose_l2({"title": "test"})
        assert "branches" in result
        assert "containers" in result
        assert "patches" in result
        assert "queue" in result
        assert mock_call.call_count == 4


@pytest.mark.asyncio
async def test_decompose_l2_skill_failure():
    with patch("services.call_skill", new_callable=AsyncMock) as mock_call:
        mock_call.side_effect = Exception("Skill error")
        with pytest.raises(Exception):
            await decompose_l2({"title": "test"})