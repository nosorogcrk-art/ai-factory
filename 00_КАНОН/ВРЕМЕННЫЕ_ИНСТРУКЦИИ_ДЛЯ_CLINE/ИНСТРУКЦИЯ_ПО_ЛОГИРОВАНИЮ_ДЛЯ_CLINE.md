## 📋 ИНСТРУКЦИЯ ПО ЛОГИРОВАНИЮ (для Cline)

**Версия:** 2.0 (временная инструкция для Cline)  
**Статус:** Актуальна до внедрения внутренних агентов  
**Место хранения:** `00_КАНОН/ВРЕМЕННЫЕ_ИНСТРУКЦИИ_ДЛЯ_CLINE/ИНСТРУКЦИЯ_ПО_ЛОГИРОВАНИЮ.md`

---

### Назначение

Эта инструкция описывает, как **отправлять логи в BR18 (Log Aggregator)** из контейнера, который ты (Cline) создаёшь или дорабатываешь. Логирование в BR18 обязательно для всех контейнеров, которые производят значимые события (создание/обновление/удаление ресурсов, вызовы внешних API, ошибки).

**Важно:** Даже если BR18 временно недоступен (лог-агрегатор unhealthy), код отправки логов должен быть добавлен с проверкой `ENABLE_BR18` – чтобы в будущем включить без изменения кода.

---

## 1. Добавление переменных окружения

В файл контейнера (например, `main.py`) добавь:

```python
import os
import logging
from datetime import datetime, timezone

BR18_URL = os.getenv("BR18_URL", "http://log-aggregator:8093/api/logs")
ENABLE_BR18 = os.getenv("ENABLE_BR18", "false").lower() == "true"
```

В `docker-compose.yml` добавь переменную для контейнера:

```yaml
environment:
  - ENABLE_BR18=false   # пока false, позже включим
  - BR18_URL=http://log-aggregator:8093/api/logs
```

---

## 2. Функция отправки логов (асинхронная, с background_tasks)

Добавь в `main.py` (или отдельный модуль `logging_utils.py`):

```python
from fastapi import BackgroundTasks
import httpx

async def send_log_to_br18(event_type: str, details: dict, background_tasks: BackgroundTasks) -> None:
    """Отправляет лог в BR18 асинхронно, если ENABLE_BR18 = true."""
    if not ENABLE_BR18:
        return
    async def _send():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    BR18_URL,
                    json={
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "service": "C?.?",  # замени на реальный ID контейнера, например "C-TG-1.1"
                        "event_type": event_type,
                        "details": details
                    },
                    timeout=5.0
                )
        except Exception as e:
            # Логируем ошибку отправки в локальный лог (чтобы не потерять)
            logger.error(f"Failed to send log to BR18: {e}")
    background_tasks.add_task(_send)
```

**Примечания:**
- Используй `BackgroundTasks` FastAPI, чтобы не блокировать ответ клиента.
- В `event_type` указывай короткое имя события: `"account_created"`, `"keyword_added"`, `"api_call_failed"` и т.п.
- В `details` передавай структурированные данные (словарь).

---

## 3. Использование в эндпоинтах

Пример для эндпоинта создания аккаунта:

```python
@app.post("/accounts", status_code=201)
async def create_account(account_data: AccountCreate, background_tasks: BackgroundTasks):
    try:
        account = await services.create_account(account_data)
        # Отправляем лог в BR18
        await send_log_to_br18(
            "account_created",
            {"account_id": account.id, "phone": account_data.phone},
            background_tasks
        )
        return account
    except Exception as e:
        await send_log_to_br18(
            "account_create_failed",
            {"error": str(e), "phone": account_data.phone},
            background_tasks
        )
        raise HTTPException(status_code=500, detail="Internal error")
```

**Обязательные события для логирования:**
- Любое изменение данных (создание, обновление, удаление).
- Вызовы внешних API (Telegram, GitHub, другие микросервисы) – успешные и с ошибками.
- Ошибки валидации (400) и внутренние ошибки (500).

---

## 4. Локальное логирование (в дополнение к BR18)

Параллельно с отправкой в BR18, веди локальный лог через стандартный `logging`:

```python
import logging

logger = logging.getLogger(__name__)

# в эндпоинте:
logger.info(f"Account created: {account.id}")
```

Локальные логи сохраняются в `01_ЦЕХ/01_ЖУРНАЛЫ/{container_name}.log`. Это дублирование – на случай, если BR18 недоступен.

---

## 5. Тестирование логирования

В тестах (особенно интеграционных) нужно **мокать** `send_log_to_br18`, чтобы не слать реальные запросы:

```python
from unittest.mock import patch

@patch("main.send_log_to_br18")
async def test_create_account_logging(mock_send_log):
    response = client.post("/accounts", json={"phone": "+123"})
    assert response.status_code == 201
    mock_send_log.assert_called_once()
    args, _ = mock_send_log.call_args
    assert args[0] == "account_created"
```

Для E2E-тестов с LLM-судьёй можно проверять, что логи отправляются (через проверку в BR18, если он доступен в тестовой среде).

---

## 6. Что делать, если BR18 недоступен (unhealthy)

- В коде уже есть `ENABLE_BR18 = false` по умолчанию. Пока BR18 не починен, отправка логов будет пропускаться без ошибок.
- Когда BR18 станет здоровым (см. отчёт Cline от 05.04.2026), нужно будет:
  - Установить `ENABLE_BR18=true` в `docker-compose.yml` для всех контейнеров.
  - Перезапустить контейнеры.
  - Проверить, что логи появляются в BR18 (через его API).

---

## 7. Проверка после реализации

После того как ты добавил логирование в контейнер:

1. Запусти контейнер с `ENABLE_BR18=false` – убедись, что код работает без ошибок.
2. Временно установи `ENABLE_BR18=true` и выполни действие, которое должно отправить лог. Проверь, что в логах контейнера нет ошибок отправки.
3. Если BR18 работает (например, `curl http://localhost:8193/health` → 200), то запроси его API `/api/logs` и убедись, что лог появился.

---

## 8. Обязательность выполнения

Этот пункт **включён в чек-лист для Cline** (`ЧЕК_ЛИСТ_ДЛЯ_CLINE.md`). Без добавления функции `send_log_to_br18` и вызовов в эндпоинтах контейнер не будет считаться готовым, если он относится к категории «производящий значимые события».

Исключение: статические фронтенд-контейнеры или простые прокси – для них логирование не обязательно (но желательно).

---

**Конец документа.**