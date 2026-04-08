import pytest
import sys
import os
from unittest.mock import AsyncMock, patch
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from external_search import search_github, search_arxiv, fetch_rss_feeds

@pytest.mark.asyncio
async def test_search_github_success():
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=AsyncMock(status_code=200, json=lambda: {"items": [{"full_name": "test/repo"}]}))):
        results = await search_github("test", limit=1)
        assert len(results) == 1
        assert results[0]["source"] == "github"

@pytest.mark.asyncio
async def test_search_arxiv_success():
    xml_response = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title><id>http://test.com</id><summary>Test</summary><published>2026-04-07</published></entry></feed>'
    with patch("httpx.AsyncClient.get", AsyncMock(return_value=AsyncMock(status_code=200, text=xml_response))):
        results = await search_arxiv("test", limit=1)
        assert len(results) == 1
        assert results[0]["source"] == "arxiv"

@pytest.mark.asyncio
async def test_fetch_rss_feeds(mocker):
    mock_feed = mocker.Mock()
    mock_feed.entries = [{"title": "Test", "link": "http://test.com", "summary": "summary", "published": "2026-04-07"}]
    with patch("feedparser.parse", return_value=mock_feed):
        results = await fetch_rss_feeds(["http://example.com/rss"], limit_per_feed=1)
        assert len(results) == 1
        assert results[0]["source"] == "rss"