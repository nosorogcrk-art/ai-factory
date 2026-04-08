import os
import json
import logging
import httpx
import sys
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))

client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT)


async def send_log_to_br18(event_type: str, details: dict):
    """Отправляет лог в BR18 (Log Aggregator)."""
    BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
    log_entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "service": "C9.4", "event_type": event_type, "details": details}
    try:
        await client.post(BR18_URL, json=log_entry)
    except Exception as e:
        logger.error(f"Failed to send log to BR18: {e}")


async def _call_llm(messages: list) -> str:
    """Вызывает DeepSeek API и возвращает ответ."""
    if not DEEPSEEK_API_KEY:
        logger.warning("DEEPSEEK_API_KEY not set, using fallback response")
        await send_log_to_br18("llm_fallback", {"reason": "DEEPSEEK_API_KEY not set"})
        return "Привет! Я помогу вам сформулировать задачу для разработки программного обеспечения. Расскажите, что именно нужно сделать?"
    
    try:
        resp = await client.post(
            DEEPSEEK_URL,
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={"model": "deepseek-chat", "messages": messages, "temperature": 0.7, "max_tokens": 1000}
        )
        resp.raise_for_status()
        data = resp.json()
        assistant_message = data["choices"][0]["message"]["content"]
        # Безусловное логирование raw ответа как требуется в задании
        logger.info(f"DeepSeek RAW response: {assistant_message}")
        print(f"DEEPSEEK_RAW: {assistant_message}", flush=True)
        sys.stdout.flush()
        await send_log_to_br18("llm_response", {"response": assistant_message[:200]})
        with open("/tmp/deepseek_raw.log", "a") as f:
            f.write(f"RAW: {assistant_message}\n\n")
        return assistant_message
    except Exception as e:
        logger.error(f"DeepSeek API error: {e}")
        await send_log_to_br18("llm_error", {"error": str(e)})
        return "Извините, сервис временно недоступен. Пожалуйста, попробуйте позже или обратитесь к администратору."


def _parse_l2_response(assistant_message: str) -> Tuple[bool, Optional[dict]]:
    """Парсит ответ LLM, определяя является ли он JSON L2."""
    # Очищаем ответ от маркеров Markdown (```json ... ```), если они есть
    cleaned = re.sub(r'^```json\s*|\s*```$', '', assistant_message.strip())
    print(f"DEBUG _parse_l2_response: cleaned length {len(cleaned)}")
    
    # Попытка распарсить как JSON
    try:
        parsed = json.loads(cleaned)
        print(f"DEBUG Parsed JSON response: {json.dumps(parsed, ensure_ascii=False)[:500]}")
        logger.info(f"Parsed JSON response: {json.dumps(parsed, ensure_ascii=False)[:500]}")
    except json.JSONDecodeError as e:
        print(f"DEBUG Response is not valid JSON: {e}")
        logger.info(f"Response is not valid JSON: {e}")
        return False, None
    
    # Проверяем наличие обязательных полей title и description
    if isinstance(parsed, dict) and "title" in parsed and "description" in parsed:
        print(f"DEBUG Detected L2 with title: {parsed.get('title')}")
        logger.info(f"Detected L2 with title: {parsed.get('title')}, description length: {len(parsed.get('description', ''))}")
        logger.info(f"L2 keys: {list(parsed.keys())}")
        return True, parsed
    else:
        print(f"DEBUG JSON parsed but missing title or description fields. Keys: {list(parsed.keys())}")
        logger.info(f"JSON parsed but missing title or description fields. Keys: {list(parsed.keys())}")
        return False, None
