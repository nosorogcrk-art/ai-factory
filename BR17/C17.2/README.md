# Skill Version Control (C17.2)

Версионирование навыков через Git-репозиторий.

## API

- `GET /health` – проверка здоровья
- `POST /commit/{skill_id}` – создать коммит для навыка
- `GET /history/{skill_id}` – история коммитов
- `GET /file/{skill_id}?ref=<hash>` – получить файл на определённой версии
- `GET /diff/{skill_id}?from_hash=<h1>&to_hash=<h2>` – diff между версиями
- `POST /rollback/{skill_id}?to_hash=<h>` – откат к версии

## Переменные окружения

- `BR18_URL` – URL лог-агрегатора (по умолчанию `http://log-aggregator:8093/api/logs`)
- `ENABLE_BR18` – включить отправку логов (true/false)

## Запуск

```bash
docker-compose up -d skill-version-control
Тестирование
bash
pytest tests/