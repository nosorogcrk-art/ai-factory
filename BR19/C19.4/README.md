# A/B Tester (C19.4)

Платформа для проведения A/B-тестов промптов и навыков.

## API

- `GET /health` – проверка здоровья
- `POST /experiments` – создать эксперимент
- `GET /experiments` – список экспериментов
- `GET /experiments/{id}` – детали эксперимента
- `PATCH /experiments/{id}` – обновить статус или параметры
- `GET /experiments/{id}/stats` – статистика назначений
- `POST /experiments/{id}/assign?user_id=xxx` – назначить вариант пользователю

## Переменные окружения

- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов (true/false)
- `DB_PATH` – путь к SQLite (по умолчанию `/data/ab_tester.db`)
- `PORT` – порт сервера (по умолчанию 8106)

## Запуск

```bash
docker-compose up -d ab-tester
Тестирование
bash
pytest tests/