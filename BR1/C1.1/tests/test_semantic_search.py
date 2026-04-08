import pytest
import sys
import os
from unittest.mock import AsyncMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from semantic_search import find_similar_projects, provide_hints_for_new_project

@pytest.mark.asyncio
async def test_find_similar_projects_success():
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: {"results": [{"id": "proj_1"}]}))):
        result = await find_similar_projects("test query")
        assert len(result) == 1

@pytest.mark.asyncio
async def test_find_similar_projects_failure():
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Network error"))):
        result = await find_similar_projects("test query")
        assert result == []

@pytest.mark.asyncio
async def test_provide_hints_for_new_project(tmp_path):
    with patch("semantic_search.find_similar_projects", AsyncMock(return_value=[{"id": "proj_1"}])), \
         patch("semantic_search.extract_hints_from_project", AsyncMock(return_value={"project_id": "proj_1", "l2": None})), \
         patch("semantic_search.HINTS_DIR", tmp_path):
        hints = await provide_hints_for_new_project("test_proj", "initial query")
        assert len(hints) == 1
        assert (tmp_path / "test_proj_hints.json").exists()