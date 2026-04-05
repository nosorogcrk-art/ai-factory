# Log Analyzer (C19.1)

Анализ логов, кластеризация ошибок с эмбеддингами, выявление паттернов, логирование в BR18.

## API

- `GET /health` – проверка здоровья
- `POST /cluster` – запуск кластеризации ошибок
- `GET /clusters` – список кластеров
- `GET /clusters/{id}` – детали кластера
- `GET /clusters/statistics` – статистика
- `POST /patterns/analyze` – анализ паттернов
- `GET /patterns` – список паттернов
- `GET /jobs` – статус задач

## Переменные окружения

- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов (true/false)
- `LOG_SOURCE_DIR` – папка с логами (по умолчанию `/data/logs`)
- `DB_PATH` – путь к SQLite
- `PORT` – порт сервера (по умолчанию 8101)

## Запуск

```bash
docker-compose up -d log-analyzer
Тестирование
bash
pytest tests/