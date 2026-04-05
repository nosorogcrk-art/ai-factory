# C4.4 Dialogue Console

Веб‑интерфейс для диалога с выбором проекта.

## Запуск
```bash
docker build -t dialogue-console .
docker run -p 8112:8112 dialogue-console
```

## Переменные окружения
- `PORT` – порт для веб‑сервера (по умолчанию 8112)

## Зависимости
- C2.6 Project Memory (порт 8108) – для управления проектами и историей
- C9.4 Dialogue Manager (порт 8111) – для обработки сообщений
