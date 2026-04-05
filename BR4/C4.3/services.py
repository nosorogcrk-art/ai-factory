import json
import logging
import httpx
from typing import Dict, Any

logger = logging.getLogger(__name__)


async def call_handover(method: str, endpoint: str, data: dict = None, base_url: str = None) -> Dict[str, Any]:
    """
    Выполняет запрос к handover API.

    Args:
        method: HTTP метод (GET или POST).
        endpoint: Путь эндпоинта.
        data: Тело запроса для POST.
        base_url: Базовый URL handover.

    Returns:
        Словарь с ответом или ошибкой.
    """
    if base_url is None:
        base_url = "http://handover:8080"
    url = f"{base_url}{endpoint}"
    try:
        async with httpx.AsyncClient() as client:
            if method == "GET":
                resp = await client.get(url, timeout=5.0)
            else:
                resp = await client.post(url, json=data, timeout=5.0)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        try:
            error_detail = e.response.json()
            return {"error": error_detail.get("detail", str(e))}
        except:
            return {"error": str(e)}
    except Exception as e:
        return {"error": str(e)}


def parse_command(command: str) -> dict:
    """
    Разбирает строку команды.

    Args:
        command: Строка команды.

    Returns:
        Словарь с ключами 'cmd' и 'args'.
    """
    parts = command.strip().split()
    if not parts:
        return {"cmd": "", "args": []}
    return {"cmd": parts[0].lower(), "args": parts[1:]}