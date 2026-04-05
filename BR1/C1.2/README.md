# C1.2 Patch Architect

FastAPI-сервис для автоматического разбиения задач на атомарные патчи.

## Запуск

```bash
docker build -t patch-architect .
docker run -p 8085:8085 -v ./01_ЦЕХ:/app/01_ЦЕХ patch-architect
Переменные окружения
Переменная	Значение по умолчанию	Назначение
PORT	8085	Порт сервиса
API
GET /health – проверка работоспособности

POST /decompose – разбиение задачи на патчи

Тело запроса:

json
{
  "description": "Описание задачи",
  "context": { "task_id": "DIALOG-xxx" }
}
Ответ:

json
{
  "patches": ["IMP-20260324-001", ...],
  "status": "ok"
}