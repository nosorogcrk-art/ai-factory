#!/usr/bin/env python3
"""
indexer.py – индексатор документов для семантической памяти.
Отслеживает изменения в 00_КАНОН/ и 01_ЦЕХ/, обновляет векторное хранилище.
"""

import os
import re
import time
import json
import logging
import threading
import sys
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import chromadb
from embedding_model import get_encoder

VECTOR_STORE_DIR = Path("00_ПАМЯТЬ/ВЕКТОРЫ")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/indexer.log")
WATCH_DIRS = [Path("00_КАНОН"), Path("01_ЦЕХ")]
COLLECTION_NAME = "documents"
CONFIG_FILE = Path("00_КАНОН/Конфиги/memory_config.json")

if CONFIG_FILE.exists():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
else:
    config = {}

IGNORE_PATTERNS = config.get("ignore_patterns", [
    r".*\.gitkeep$",
    r".*prompt_hashes\.json$",
    r".*SYSTEM_REGISTRY\.json$",
    r".*\.log$",
    r".*\.DS_Store$",
    r".*\.(jpg|jpeg|png|gif|bmp|ico|pdf|zip|tar|gz|7z|rar|exe|dll|so|bin|class|pyc)$"
])

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
collection = client.get_or_create_collection(COLLECTION_NAME)
encoder = get_encoder()

def should_ignore(file_path: Path) -> bool:
    for pattern in IGNORE_PATTERNS:
        if re.match(pattern, str(file_path)):
            return True
    return False

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
    else:
        return content

def get_title(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if line:
            return line[:100]
    return ""

def encode_with_retry(text, retries=3, delay=1):
    for attempt in range(retries):
        try:
            return encoder.encode(text).tolist()
        except Exception as e:
            logging.warning(f"Encoding attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                raise

def index_file(file_path: Path):
    if should_ignore(file_path):
        return
    text = extract_text(file_path)
    if text is None or not text.strip():
        return
    embedding = encode_with_retry(text)
    metadata = {
        "path": str(file_path),
        "source": "internal",
        "timestamp": str(file_path.stat().st_mtime),
        "title": get_title(text)
    }
    doc_id = str(file_path)

    try:
        collection.delete(ids=[doc_id])
    except:
        pass

    collection.add(ids=[doc_id], embeddings=[embedding], metadatas=[metadata])
    logging.info(f"Indexed {doc_id}")

def remove_file(file_path: Path):
    doc_id = str(file_path)
    try:
        collection.delete(ids=[doc_id])
        logging.info(f"Removed {doc_id}")
    except Exception as e:
        logging.error(f"Failed to remove {doc_id}: {e}")

class ChangeHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if not event.is_directory and not should_ignore(Path(event.src_path)):
            index_file(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and not should_ignore(Path(event.src_path)):
            index_file(Path(event.src_path))

    def on_deleted(self, event):
        if not event.is_directory:
            remove_file(Path(event.src_path))

def full_scan():
    logging.info("Starting full scan...")
    for base in WATCH_DIRS:
        if not base.exists():
            continue
        for root, _, files in os.walk(base):
            for file in files:
                file_path = Path(root) / file
                if not should_ignore(file_path):
                    index_file(file_path)
    logging.info("Full scan completed.")

def periodic_scan(interval=3600):
    while True:
        time.sleep(interval)
        full_scan()

def main():
    full_scan()
    observer = Observer()
    for watch_dir in WATCH_DIRS:
        if watch_dir.exists():
            observer.schedule(ChangeHandler(), str(watch_dir), recursive=True)
    observer.start()
    logging.info("Watchdog started. Monitoring directories: %s", [str(d) for d in WATCH_DIRS if d.exists()])

    t = threading.Thread(target=periodic_scan, args=(3600,), daemon=True)
    t.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
