import json
import logging
import httpx
import feedparser
import os
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

PROJECT_MEMORY_URL = "http://project-memory:8108"
INDEX_ENDPOINT = f"{PROJECT_MEMORY_URL}/index"

# Конфигурация источников (можно вынести в переменные окружения)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
ARXIV_CATEGORIES = ["cs.AI", "cs.SE", "cs.LG"]
RSS_FEEDS = [
    "https://habr.com/ru/rss/hub/python/all/",
    "https://medium.com/feed/tag/ai",
    "https://dev.to/feed/tag/python"
]
RESULTS_DIR = Path("01_ЦЕХ/ВНЕШНИЕ_РЕСУРСЫ")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

async def search_github(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Ищет репозитории на GitHub по запросу."""
    if not query:
        return []
    url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "order": "desc", "per_page": limit}
    headers = {"Accept": "application/vnd.github.v3+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            results = []
            for item in items:
                results.append({
                    "source": "github",
                    "title": item.get("full_name"),
                    "url": item.get("html_url"),
                    "description": item.get("description", ""),
                    "stars": item.get("stargazers_count"),
                    "language": item.get("language"),
                    "created_at": item.get("created_at"),
                    "updated_at": item.get("updated_at")
                })
            logger.info(f"GitHub search for '{query}' returned {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"GitHub API error: {e}")
        return []

async def search_arxiv(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Ищет статьи на arXiv по запросу."""
    if not query:
        return []
    url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "submittedDate",
        "sortOrder": "descending"
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15.0)
            resp.raise_for_status()
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            results = []
            for entry in root.findall("atom:entry", ns):
                title = entry.find("atom:title", ns).text
                link = entry.find("atom:id", ns).text
                summary = entry.find("atom:summary", ns).text[:500]
                published = entry.find("atom:published", ns).text
                results.append({
                    "source": "arxiv",
                    "title": title,
                    "url": link,
                    "summary": summary,
                    "published": published
                })
            logger.info(f"arXiv search for '{query}' returned {len(results)} results")
            return results
    except Exception as e:
        logger.error(f"arXiv API error: {e}")
        return []

async def fetch_rss_feeds(feeds: List[str], limit_per_feed: int = 3) -> List[Dict[str, Any]]:
    """Парсит RSS-ленты и возвращает статьи."""
    results = []
    for feed_url in feeds:
        try:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit_per_feed]:
                results.append({
                    "source": "rss",
                    "source_url": feed_url,
                    "title": entry.get("title"),
                    "url": entry.get("link"),
                    "summary": entry.get("summary", "")[:500],
                    "published": entry.get("published")
                })
            logger.info(f"RSS feed {feed_url} fetched, got {len(parsed.entries[:limit_per_feed])} items")
        except Exception as e:
            logger.error(f"Failed to parse RSS feed {feed_url}: {e}")
    return results

async def index_external_article(article: Dict[str, Any]) -> bool:
    """Индексирует внешнюю статью в C2.6."""
    doc_id = f"ext_{article['source']}_{hash(article['url']) % 1000000}"
    content = f"{article.get('title', '')}\n\n{article.get('description', article.get('summary', ''))}"
    metadata = {
        "source": article.get("source"),
        "title": article.get("title"),
        "url": article.get("url"),
        "date": article.get("published") or article.get("created_at"),
        "type": "external_knowledge"
    }
    payload = {
        "documents": [{
            "id": doc_id,
            "content": content,
            "metadata": metadata
        }]
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(INDEX_ENDPOINT, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info(f"Indexed external article: {article['title'][:50]}")
            return True
    except Exception as e:
        logger.error(f"Failed to index external article: {e}")
        return False

async def collect_external_knowledge(project_keywords: List[str] = None):
    """
    Собирает внешние знания по ключевым словам (если не заданы – берёт популярные теги из проектов).
    Сохраняет результаты в C2.6 и локально.
    """
    logger.info("Starting external knowledge collection")
    all_items = []
    # Если нет ключевых слов, используем общие (можно настроить)
    if not project_keywords:
        project_keywords = ["python fastapi", "telegram bot", "microservices", "ai assistant"]
    for keyword in project_keywords[:3]:  # ограничим количество запросов
        github_results = await search_github(keyword, limit=3)
        arxiv_results = await search_arxiv(keyword, limit=2)
        all_items.extend(github_results)
        all_items.extend(arxiv_results)
    # RSS фиды (без ключевых слов)
    rss_results = await fetch_rss_feeds(RSS_FEEDS, limit_per_feed=3)
    all_items.extend(rss_results)
    
    # Индексируем и сохраняем локально
    indexed_count = 0
    for item in all_items:
        if await index_external_article(item):
            indexed_count += 1
    # Сохраняем полный результат в JSON для отладки
    timestamp = datetime.now().strftime("%Y-%m-%d")
    report_file = RESULTS_DIR / f"external_collection_{timestamp}.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "items": all_items,
            "indexed_count": indexed_count
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"External collection finished, indexed {indexed_count} items")
    return all_items

async def external_search_scheduler(interval_seconds: int = 86400):
    """Фоновый планировщик, запускающий сбор внешних знаний раз в сутки."""
    while True:
        await collect_external_knowledge()
        await asyncio.sleep(interval_seconds)