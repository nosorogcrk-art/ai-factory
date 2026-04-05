#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
external_to_indexer.py – передача внешних файлов в индексатор C2.2.
"""

import json
import logging
import re
import sys
from pathlib import Path
import chromadb
from embedding_model import get_encoder

VECTOR_STORE_DIR = Path("00_ПАМЯТЬ/ВЕКТОРЫ")
COLLECTION_NAME = "documents"
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/external_to_indexer.log")

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
collection = client.get_or_create_collection(COLLECTION_NAME)
encoder = get_encoder()

def extract_text(file_path: Path) -> str | None:
    ext = file_path.suffix.lower()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        logging.error(f"Error reading {file_path}: {e}")
        return None

    if ext == ".md":
        content = re.sub(r'\[\[(.*?)\]\]', r'\1', content)
        content = re.sub(r'^#+\s*', '', content, flags=re.MULTILINE)
        content = re.sub(r'^[\*\-\+]\s+', '', content, flags=re.MULTILINE)
    return content

def get_title(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line[:100]
    return ""

def index_file(file_path: Path):
    if not file_path.exists():
        logging.warning(f"File {file_path} does not exist, skipping.")
        return
    text = extract_text(file_path)
    if text is None or not text.strip():
        return
    embedding = encoder.encode(text).tolist()
    metadata = {
        "source": "external",
        "path": str(file_path),
        "timestamp": str(file_path.stat().st_mtime),
        "title": get_title(text),
        "source_type": "external"
    }
    doc_id = str(file_path)
    try:
        collection.delete(ids=[doc_id])
    except:
        pass
    collection.add(ids=[doc_id], embeddings=[embedding], metadatas=[metadata])
    logging.info(f"Indexed external file {doc_id}")

def process_batch(batch_file: Path):
    if not batch_file.exists():
        logging.error(f"Batch file {batch_file} not found.")
        return
    with open(batch_file, "r") as f:
        file_list = json.load(f)
    for file_path_str in file_list:
        index_file(Path(file_path_str))
    logging.info(f"Processed {len(file_list)} external files.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        batch_file = Path(sys.argv[1])
    else:
        batch_file = Path("00_ПАМЯТЬ/Внешние/latest_batch.json")
    process_batch(batch_file)
