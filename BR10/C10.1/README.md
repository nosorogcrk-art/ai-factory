# C10.1 Integrator

Сборка продукта из атомарных патчей.

## Запуск

```bash
docker build -t integrator .
docker run -p 8096:8096 -v ./02_ПРОДУКТ:/app/02_ПРОДУКТ integrator
Переменные окружения
Переменная	Значение по умолчанию	Назначение
PORT	8096	Порт сервиса
API
GET /health – проверка работоспособности

POST /build – запуск сборки

Тело запроса:

json
{
  "patch_ids": ["IMP-001", ...],
  "check_skills": true,
  "run_tests": true
}
Ответ:

json
{
  "status": "started",
  "message": "Build started"
}