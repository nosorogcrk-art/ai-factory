#!/usr/bin/env python3
"""
init_vector_store.py – инициализация векторного хранилища Chroma.
Создаёт директорию, запускает Chroma persistent client и создаёт коллекцию.
"""

import os
import sys
import logging
from pathlib import Path
import chromadb

VECTOR_STORE_DIR = Path("00_ПАМЯТЬ/ВЕКТОРЫ")
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/vector_store_init.log")
COLLECTION_NAME = "documents"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def init_vector_store():
    VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
    logging.info(f"Vector store directory: {VECTOR_STORE_DIR}")

    try:
        client = chromadb.PersistentClient(path=str(VECTOR_STORE_DIR))
        logging.info("Chroma client created.")
    except Exception as e:
        logging.error(f"Failed to create Chroma client: {e}")
        sys.exit(1)

    try:
        collection = client.get_collection(COLLECTION_NAME)
        logging.info(f"Collection '{COLLECTION_NAME}' already exists.")
    except ValueError:
        collection = client.create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logging.info(f"Collection '{COLLECTION_NAME}' created.")
    except Exception as e:
        logging.error(f"Error accessing collection: {e}")
        sys.exit(1)

    try:
        test_id = "test_doc"
        test_embedding = [0.0] * 384
        test_metadata = {"source": "test", "path": "/dev/null"}
        collection.add(ids=[test_id], embeddings=[test_embedding], metadatas=[test_metadata])
        results = collection.query(query_embeddings=[test_embedding], n_results=1)
        if results['ids'][0][0] == test_id:
            logging.info("Test query passed.")
        else:
            logging.warning("Test query returned unexpected result.")
        collection.delete(ids=[test_id])
        logging.info("Test record cleaned up.")
    except Exception as e:
        logging.error(f"Test failed: {e}")
        sys.exit(1)

    logging.info("Vector store initialized successfully.")
    print("✅ Vector store ready.")

if __name__ == "__main__":
    init_vector_store()
