# Packager (C10.3)

Упаковщик кода в ZIP-архивы.

## Запуск
```bash
docker-compose up -d packager
```

## Пример запроса
```bash
curl -X POST http://localhost:8093/package -H "Content-Type: application/json" -d '{
  "project_id": "my_project",
  "files": [{"filename": "main.py", "content": "print(1)"}]
}'
```

## Healthcheck
```bash
curl http://localhost:8093/health