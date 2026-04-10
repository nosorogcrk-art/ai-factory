# Навык code_generation

## Описание
Навык генерирует код (Python, Dockerfile, тесты) на основе спецификации L5 (архитектура, контейнеры, патчи).

## Входные данные
JSON с полем `spec` (спецификация L5: структура контейнера, зависимости, эндпоинты, логика).

Пример входных данных:
```json
{
  "spec": {
    "container_id": "C10.1",
    "name": "Integrator",
    "description": "Сервис интеграции навыков",
    "dependencies": ["httpx", "fastapi"],
    "endpoints": [
      {
        "path": "/generate",
        "method": "POST",
        "description": "Генерация кода из L5 спецификации"
      }
    ],
    "logic": "Асинхронный вызов C7.4 для генерации кода",
    "files_to_generate": ["main.py", "services.py", "Dockerfile", "requirements.txt", "tests/test_api.py"]
  }
}
```

## Требования
1. Сгенерировать файлы (main.py, models.py, services.py, Dockerfile, requirements.txt, тесты).
2. Код должен соответствовать стандартам проекта:
   - Использовать асинхронные вызовы (httpx.AsyncClient)
   - Не использовать синхронные вызовы (requests запрещены)
   - Добавлять healthcheck эндпоинты
   - Включать обработку ошибок с HTTPException
3. Формат ответа: JSON с полем `files` – массив объектов `{"path": "...", "content": "..."}`.

## Формат ответа
```json
{
  "files": [
    {
      "path": "main.py",
      "content": "from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get('/health')\nasync def health():\n    return {'status': 'ok'}"
    },
    {
      "path": "Dockerfile",
      "content": "FROM python:3.11-slim\n\nWORKDIR /app\n\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\n\nCOPY . .\n\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]"
    }
  ]
}
```

## Примеры ожидаемой структуры

### FastAPI-приложение
```python
from fastapi import FastAPI, HTTPException
import httpx

app = FastAPI()

@app.post("/generate")
async def generate_code(request: dict):
    # Логика генерации
    pass

@app.get("/health")
async def health():
    return {"status": "ok"}
```

### Тесты
```python
import pytest
from unittest.mock import AsyncMock, patch
from services import generate_code_from_l5

@pytest.mark.asyncio
async def test_generate_code_success():
    # Тест успешной генерации
    pass
```

## Запрещено
- Использовать `kill`, `rm`, опасные команды в коде
- Использовать синхронные HTTP-клиенты (`requests`)
- Генерировать код с потенциальными уязвимостями
- Нарушать архитектурные принципы проекта

## Примечания
- Все зависимости должны быть указаны в requirements.txt
- Dockerfile должен использовать многостадийную сборку, если это уместно
- Тесты должны покрывать основные сценарии (минимум 3 теста)
- Код должен быть читаемым и документированным