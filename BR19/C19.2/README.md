# Prompt Optimizer (C19.2)

Генерация улучшенных версий промптов на основе анализа логов и внешних практик.

## API

- `GET /health` – проверка здоровья
- `POST /optimize/{prompt_id}` – запустить оптимизацию
- `GET /optimize/{prompt_id}/status` – статус задач
- `GET /candidates` – список кандидатов
- `GET /jobs/{job_id}/candidates` – кандидаты по задаче
- `POST /candidates/{id}/promote` – отправить в A/B тестер
- `POST /optimize/{job_id}/cancel` – отмена задачи

## Переменные окружения

- `LOG_ANALYZER_URL` – URL C19.1 (по умолчанию `http://log-analyzer:8101`)
- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов
- `PORT` – порт сервера (по умолчанию 8102)

## Запуск

```bash
docker-compose up -d prompt-optimizer
Тестирование
bash
pytest tests/