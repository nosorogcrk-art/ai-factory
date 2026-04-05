# Skill Registry (C17.1)

Реестр навыков – централизованное хранение метаданных навыков с CRUD API, фильтрацией, пагинацией, статистикой и логированием в BR18.

## API

- `GET /health` – проверка здоровья
- `GET /skills` – список навыков (параметры: `status`, `tag`, `limit`, `offset`, `include_deleted`)
- `GET /skills/{id}` – получить навык
- `POST /skills` – создать навык
- `PUT /skills/{id}` – полностью обновить навык
- `PATCH /skills/{id}` – частично обновить навык
- `DELETE /skills/{id}` – мягкое удаление
- `GET /skills/stats` – статистика

## Переменные окружения

- `BR18_URL` – URL лог-агрегатора (по умолчанию `http://log-aggregator:8093/api/logs`)
- `ENABLE_BR18` – включить отправку логов (true/false)
- `PORT` – порт сервера (по умолчанию 8088)

## Запуск

```bash
docker-compose up -d skill-registry
Тестирование
bash
pytest tests/