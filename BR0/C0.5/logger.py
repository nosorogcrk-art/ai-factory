#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
logger.py – настройка логирования для System Mapper.
Отправляет логи в файл и в BR18 (если настроено).
"""

import os
import logging
import httpx
from pathlib import Path
from datetime import datetime, timezone

LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/system_mapper.log")
BR18_URL = os.getenv("BR18_URL", "http://br18:8080/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"

LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("system_mapper")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

async def send_log_to_br18(event_type: str, details: dict):
    if not ENABLE_BR18:
        return
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "C0.5",
        "event_type": event_type,
        "details": details
    }
    try:
        async with httpx.AsyncClient() as client:
            await client.post(BR18_URL, json=log_entry, timeout=2.0)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")