# Skill Updater (C19.3)

Автоматическое улучшение навыков на основе анализа логов и успешных кейсов.

## API

- `GET /health` – проверка здоровья
- `POST /skills/{skill_id}/improve` – запустить улучшение навыка
- `GET /improvement_jobs/{job_id}` – статус задачи
- `POST /improvement_jobs/{job_id}/cancel` – отмена задачи
- `GET /improvement_proposals` – список предложений
- `POST /improvement_proposals/{id}/approve` – применить предложение

## Переменные окружения

- `LOG_ANALYZER_URL` – URL C19.1 (по умолчанию `http://log-analyzer:8101`)
- `SKILL_REGISTRY_URL` – URL C17.1 (по умолчанию `http://skill-registry:8088`)
- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов
- `PORT` – порт сервера (по умолчанию 8104)

## Запуск

```bash
docker-compose up -d skill-updater
Тестирование
bash
pytest tests/