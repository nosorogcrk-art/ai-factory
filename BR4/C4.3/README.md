# C4.3 Command Console

Веб-интерфейс для отправки команд агентам и системным компонентам завода.

## Запуск
```bash
docker build -t command-console .
docker run -p 8100:8095 -v ./01_ЦЕХ:/app/01_ЦЕХ command-console
Переменные окружения
PORT – порт сервиса (по умолчанию 8100)

HANDOVER_URL – адрес BR7 handover (http://handover:8080)

BR18_URL – адрес Log Aggregator (http://log-aggregator:8093/api/logs)

API
GET /health – проверка работоспособности

POST /api/command – выполнение команды (тело: {"command": "..."})

GET / – HTML-страница консоли

Тестирование
bash
pytest -v
