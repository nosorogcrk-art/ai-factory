import json
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Indexer", version="1.0")
logger = logging.getLogger(__name__)

class IndexRequest(BaseModel):
    documents: list[str]

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/index")
async def index_documents(req: IndexRequest):
    indexed = []
    errors = []
    for doc in req.documents:
        path = Path(doc)
        if path.exists():
            # Имитируем индексацию (можно сохранять метаданные в файл)
            logger.info(f"Indexed: {doc}")
            indexed.append(doc)
        else:
            logger.warning(f"File not found: {doc}")
            errors.append(f"Not found: {doc}")
    return {"status": "ok", "indexed_count": len(indexed), "errors": errors}