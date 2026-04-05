# C20.3 Rollback Manager

Менеджер отката для системы CI/CD завода агентов ИИ. Хранит историю успешных деплоев и выполняет откаты к предыдущим версиям при обнаружении проблем.

## Функциональность

- **Хранение истории деплоев**: Получает уведомления от C20.2 (Auto Deployer) о каждом успешном деплое
- **Ручной откат**: API для выполнения отката по команде из BR4 (Command Console)
- **Автоматический откат**: Автоматический запуск отката при получении сигнала от BR18 (Alert Manager)
- **Интеграция с GitOps**: Получение файлов версий через C20.1 (GitOps Core)
- **Применение конфигураций**: Вызов C20.5 (Environment Manager) для применения конфигураций
- **Логирование**: Отправка логов всех действий в BR18

## API Endpoints

### `POST /deployments`
Прием уведомлений о деплоях от C20.2

**Пример запроса:**
```json
{
  "deploy_id": "dep_123",
  "repository": "ai-factory",
  "commit_hash": "abc123",
  "tag": "v1.0.0",
  "environment": "production",
  "timestamp": "2024-01-01T00:00:00Z",
  "config_files": ["docker-compose.yml", "config.env"]
}
```

### `POST /rollback`
Выполнение отката

**Пример запроса:**
```json
{
  "deploy_id": "dep_123",
  "reason": "errors detected in monitoring",
  "target_version": "v0.9.0"
}
```

**Ответ:**
```json
{
  "rollback_id": "rb_456",
  "status": "started",
  "message": "Rollback initiated"
}
```

### `GET /history`
Получение истории деплоев и откатов

**Параметры:**
- `limit` (опционально): количество записей (по умолчанию 100)
- `offset` (опционально): смещение (по умолчанию 0)
- `environment` (опционально): фильтр по окружению

### `GET /health`
Проверка здоровья сервиса

## Интеграции

- **C20.1 (GitOps Core)**: Получение файлов версий
- **C20.2 (Auto Deployer)**: Получение уведомлений о деплоях
- **C20.5 (Environment Manager)**: Применение конфигураций
- **BR18 (Alert Manager)**: Получение сигналов об ошибках
- **BR4 (Command Console)**: Ручной запуск откатов

## Запуск

### Локально
```bash
cd BR20/C20.3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8107
```

### Docker
```bash
cd BR20/C20.3
docker build -t c20.3-rollback-manager .
docker run -p 8107:8107 -v $(pwd)/data:/data c20.3-rollback-manager
```

### Docker Compose
```bash
cd /Users/a1/Dev/ЗАВОД_АГЕНТОВ/ai-factory
docker-compose up -d rollback-manager
```

## Тестирование

```bash
cd BR20/C20.3
python3 -m pytest app/tests/ -v
python3 -m mypy app/ --ignore-missing-imports
python3 -m ruff check app/
```

## Конфигурация

Сервис использует SQLite для хранения истории деплоев. База данных сохраняется в `/data/rollback_history.db` в Docker или `rollback_history.db` локально.

Порт: 8107