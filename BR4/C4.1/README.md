
# C4.1 Project Dashboard

Веб-интерфейс для отображения ключевых метрик завода.

## Запуск
```bash
docker build -t dashboard .
docker run -p 8098:8094 -v ./01_ЦЕХ:/app/01_ЦЕХ dashboard
Переменные окружения
PORT – порт сервиса (по умолчанию 8098)

REGISTRY_URL – адрес BR0 Registry (по умолчанию http://registry:8000)

METRICS_URL – адрес C18.2 Metrics Dashboard (http://metrics-dashboard:8094)

SKILL_REGISTRY_URL – адрес C17.1 Skill Registry (http://skill-registry:8088)

BR18_URL – адрес Log Aggregator (http://log-aggregator:8093/api/logs)

TASK_REGISTRY_PATH – путь к реестру задач (01_ЦЕХ/ТЕКУЩИЕ_ЗАДАЧИ/task_registry.json)

API
GET /health – проверка работоспособности

GET /api/status – агрегированные метрики (JSON)

GET / – HTML-страница дашборда

Тестирование
bash
pytest -v