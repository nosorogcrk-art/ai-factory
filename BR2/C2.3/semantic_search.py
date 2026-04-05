#!/usr/bin/env python3
"""
semantic_search.py – базовый API семантического поиска (P2.1.3).
Возвращает список ID документов без метаданных.
"""

import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import chromadb
from cachetools import TTLCache
from embedding_model import get_encoder

VECTOR_STORE_DIR = Path("00_ПАМЯТЬ/ВЕКТОРЫ")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/semantic_search.log")
COLLECTION_NAME = "documents"
CACHE_SIZE = 100
CACHE_TTL = 300

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
collection = client.get_collection(COLLECTION_NAME)
encoder = get_encoder()

cache = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_TTL)

app = FastAPI(title="Semantic Search", version="0.1.0")

class SearchRequest(BaseModel):
    query: str
    k: int = 10
    filters: Optional[Dict] = None

class SearchResult(BaseModel):
    id: str
    score: float

@app.post("/search", response_model=List[SearchResult])
def search(req: SearchRequest):
    cache_key = (req.query, req.k, str(req.filters))
    if cache_key in cache:
        logging.info(f"Cache hit for query: {req.query[:50]}...")
        return cache[cache_key]

    embedding = encoder.encode(req.query).tolist()
    try:
        results = collection.query(
            query_embeddings=[embedding],
            n_results=req.k,
            where=req.filters
        )
    except Exception as e:
        logging.error(f"Chroma query failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

    output = []
    for i in range(len(results['ids'][0])):
        doc_id = results['ids'][0][i]
        distance = results['distances'][0][i]
        score = 1 / (1 + distance)
        output.append(SearchResult(id=doc_id, score=score))

    output.sort(key=lambda x: x.score, reverse=True)
    cache[cache_key] = output
    logging.info(f"Search for '{req.query[:50]}...' returned {len(output)} results")
    return output

@app.get("/health")
def health():
    return {"status": "ok"}
