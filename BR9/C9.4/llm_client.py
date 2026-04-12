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
    """
    Пытается извлечь L2 из ответа LLM.
    Возвращает (is_l2, l2_data). l2_data – словарь, если успешно.
    Поддерживает два формата:
    1. Прямой L2: {"title": "...", "description": "...", "requirements": [...], "technical_specs": {...}}
    2. Завершённый диалог: {"completed": true, "l2": {...}}
    """
    # Очистка от маркеров Markdown (```json ... ```)
    cleaned = re.sub(r'```json\s*', '', assistant_message)
    cleaned = re.sub(r'```', '', cleaned)
    cleaned = cleaned.strip()
    
    # Попытка найти JSON в тексте (если весь ответ не является JSON)
    start = cleaned.find('{')
    end = cleaned.rfind('}')
    if start != -1 and end != -1 and start < end:
        json_candidate = cleaned[start:end+1]
        try:
            data = json.loads(json_candidate)
            
            # Проверка формата 2: завершённый диалог с completed: true
            if isinstance(data, dict) and data.get("completed") is True:
                l2_data = data.get("l2")
                if isinstance(l2_data, dict) and all(k in l2_data for k in ['title', 'description', 'requirements', 'technical_specs']):
                    logger.info(f"Successfully parsed completed L2: {l2_data.get('title')}")
                    print(f"DEBUG Detected completed L2 with title: {l2_data.get('title')}")
                    return True, l2_data
                else:
                    logger.debug(f"Completed flag set but missing l2 or required fields: {data.keys()}")
                    print(f"DEBUG Completed flag set but missing l2 or required fields. Keys: {data.keys()}")
            
            # Проверка формата 1: прямой L2
            if all(k in data for k in ['title', 'description', 'requirements', 'technical_specs']):
                logger.info(f"Successfully parsed L2: {data.get('title')}")
                print(f"DEBUG Detected L2 with title: {data.get('title')}")
                return True, data
            else:
                logger.debug(f"Missing required fields in JSON: {data.keys()}")
                print(f"DEBUG JSON parsed but missing required fields. Keys: {data.keys()}")
        except json.JSONDecodeError as e:
            logger.debug(f"JSON decode error: {e}")
            print(f"DEBUG JSON decode error: {e}")
    else:
        logger.debug("No JSON object found in response")
        print(f"DEBUG No JSON object found in response, cleaned length {len(cleaned)}")
    
    return False, None
