# C20.2 Config Versioning

Сервис управления версиями конфигураций для системы CI/CD завода агентов ИИ.

## Описание

C20.2 Config Versioning предоставляет API для хранения, управления и отслеживания версий конфигурационных файлов (docker-compose.yml, переменные окружения и др.). Сервис позволяет:

- Сохранять новые версии конфигураций
- Получать историю изменений
- Сравнивать различия между версиями
- Выполнять откат к предыдущим версиям

## Технологический стек

- **Python 3.12**
- **FastAPI** - веб-фреймворк
- **SQLite** - база данных для хранения версий
- **Docker** - контейнеризация
- **Pydantic** - валидация данных
- **Pytest** - тестирование

## Структура проекта

```
BR20/C20.2/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI приложение
│   ├── models/              # Pydantic модели
│   │   ├── __init__.py
│   │   └── config.py
│   ├── services/            # Бизнес-логика
│   │   ├── __init__.py
│   │   └── config_service.py
│   ├── repositories/        # Работа с БД
│   │   ├── __init__.py
│   │   └── config_repository.py
│   └── tests/               # Тесты
│       ├── __init__.py
│       ├── test_services.py
│       └── test_api.py
├── Dockerfile
├── requirements.txt
└── README.md
```

## API Эндпоинты

### Healthcheck
- `GET /health` - проверка здоровья сервиса

### Управление конфигурациями
- `POST /configs` - создание новой версии конфигурации
- `GET /configs` - список всех конфигураций (без содержимого)
- `GET /configs/versions` - список всех версий
- `GET /configs/latest` - последняя версия конфигурации
- `GET /configs/{version}` - получение конфигурации по версии
- `DELETE /configs/{version}` - удаление конфигурации по версии

### Сравнение и откат
- `GET /configs/diff?from_version={v1}&to_version={v2}` - разница между версиями
- `POST /configs/rollback/{version}` - откат к указанной версии

## Запуск

### Локальный запуск (разработка)

1. Установите зависимости:
```bash
pip install -r requirements.txt
```

2. Запустите сервер:
```bash
cd app
uvicorn main:app --host 0.0.0.0 --port 8202 --reload
```

3. Откройте документацию API:
- Swagger UI: http://localhost:8202/docs
- ReDoc: http://localhost:8202/redoc

### Запуск в Docker

1. Соберите образ:
```bash
docker build -t c20.2-config-versioning .
```

2. Запустите контейнер:
```bash
docker run -p 8202:8202 -v $(pwd)/data:/data c20.2-config-versioning
```

## Интеграция с docker-compose

Сервис интегрирован в общий docker-compose.yml завода агентов ИИ:

```yaml
config-versioning:
  build: ./BR20/C20.2
  ports:
    - "8202:8202"
  networks:
    - factory-net
  volumes:
    - ./data/config_versioning:/data
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8202/health"]
    interval: 30s
    timeout: 5s
    retries: 3
```

## Тестирование

### Запуск тестов
```bash
cd BR20/C20.2
pytest app/tests/ -v
```

### Статический анализ
```bash
cd BR20/C20.2
mypy app/ --ignore-missing-imports
ruff check app/
```

## Примеры использования

### Создание новой версии конфигурации
```bash
curl -X POST http://localhost:8202/configs \
  -H "Content-Type: application/json" \
  -d '{
    "content": "version: '\''3.8'\''\nservices:\n  app:\n    image: nginx:latest",
    "version": "v1.0.0",
    "description": "Initial docker-compose config",
    "config_type": "docker-compose"
  }'
```

### Получение списка версий
```bash
curl http://localhost:8202/configs/versions
```

### Сравнение версий
```bash
curl "http://localhost:8202/configs/diff?from_version=v1.0.0&to_version=v1.0.1"
```

### Откат к версии
```bash
curl -X POST http://localhost:8202/configs/rollback/v1.0.0 \
  -H "Content-Type: application/json" \
  -d '{
    "target_version": "v1.0.0",
    "create_new_version": true
  }'
```

## Логирование

Сервис использует стандартный модуль logging Python. Логи записываются в стандартный вывод (stdout) и могут быть перенаправлены в систему логирования завода (BR18).

## Соответствие Золотому стандарту

✅ **Кодирование**: Python 3.12, PEP 8, аннотации типов  
✅ **Структура файлов**: разделение на models/services/repositories  
✅ **Логирование**: использование модуля logging  
✅ **Обработка ошибок**: корректные HTTP статусы  
✅ **REST API**: JSON ответы, стандартные статусы  
✅ **Тестирование**: юнит-тесты и интеграционные тесты  
✅ **Документация**: README.md, docstrings, OpenAPI  
✅ **Healthcheck**: эндпоинт /health  
✅ **Статический анализ**: mypy и ruff  

## Зависимости

- **C20.1 GitOps Core** - для интеграции с Git-репозиториями
- **BR18 Monitoring** - для логирования и мониторинга
- **BR4 Command Console** - для ручного управления через интерфейс

## Ответственный

**ГЕФЕСТ** - разработка и поддержка CI/CD компонентов.