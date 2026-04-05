# GitOps Core (C20.1)

Центральный оркестратор CI/CD: приём webhook от Git, ручной деплой, выполнение docker-compose up.

## API

- `GET /health` – проверка здоровья
- `POST /webhook` – приём Git-событий (ожидает payload с `ref` и `repository.clone_url`)
- `POST /deploy` – ручной деплой (тело: `repo_url`, `branch`, `version` опционально)
- `GET /deployments` – список деплоев
- `GET /deployments/{id}/status` – статус деплоя

## Переменные окружения

- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов
- `DB_PATH` – путь к SQLite (по умолчанию `/data/gitops.db`)
- `WEBHOOK_SECRET` – секрет для проверки webhook (опционально)
- `PORT` – порт сервера (по умолчанию 8201)

## Запуск

```bash
docker-compose up -d gitops-core
Тестирование
bash
pytest tests/