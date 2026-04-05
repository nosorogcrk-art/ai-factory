
# Skill Publisher (C17.5)

Публикатор навыков для агентов с кэшированием и интеграцией с C17.1, C17.2, C17.4.

## API

- `GET /health` – проверка здоровья
- `GET /status` – статистика кэша
- `GET /skill/{skill_id}?version=&agent_type=` – получить навык
- `POST /skills/batch` – массовое получение навыков

## Переменные окружения

- `SKILL_REGISTRY_URL` – URL C17.1 (по умолчанию `http://skill-registry:8088`)
- `SKILL_VERSION_CONTROL_URL` – URL C17.2 (по умолчанию `http://skill-version-control:8089`)
- `SKILL_TESTER_URL` – URL C17.4 (по умолчанию `http://skill-tester:8091`)
- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов
- `ENABLE_SKILL_TEST_CHECK` – проверять тестирование навыков

## Запуск

```bash
docker-compose up -d skill-publisher
Тестирование
bash
pytest tests/