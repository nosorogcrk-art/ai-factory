# C2.6 Project Memory

Хранилище проектов, сообщений и артефактов с семантическим поиском на основе Chroma и sentence-transformers.

## Запуск
```bash
docker build -t project-memory .
docker run -p 8108:8090 -v ./01_ЦЕХ:/app/01_ЦЕХ project-memory
```

## Переменные окружения
- `BR18_URL` – адрес агрегатора логов (по умолчанию `http://log-aggregator:8093/api/logs`)
- `REQUEST_TIMEOUT` – таймаут для внешних запросов (5 сек)
- `MAX_ARTIFACT_SIZE` – максимальный размер артефакта (10 МБ)
- `PROJECTS_ROOT` – корневая папка проектов (по умолчанию `01_ЦЕХ/ПРОЕКТЫ`)
- `CHROMA_PATH` – папка для Chroma (по умолчанию `01_ЦЕХ/ПРОЕКТЫ/chroma_data`)

## API
Документация OpenAPI доступна по `/docs` (порт 8108).

### Основные эндпоинты

#### Проекты
- `POST /projects` – создать проект
- `GET /projects` – список проектов
- `GET /projects/{project_id}` – получить проект
- `PATCH /projects/{project_id}` – обновить проект
- `DELETE /projects/{project_id}` – удалить проект

#### Сообщения
- `POST /projects/{project_id}/messages` – добавить сообщение
- `GET /projects/{project_id}/messages` – получить сообщения

#### Артефакты
- `POST /projects/{project_id}/artifacts` – добавить артефакт
- `GET /projects/{project_id}/artifacts` – список артефактов
- `GET /projects/{project_id}/artifacts/{artifact_id}` – метаданные артефакта
- `GET /projects/{project_id}/artifacts/{artifact_id}/content` – содержимое артефакта
- `DELETE /projects/{project_id}/artifacts/{artifact_id}` – удалить артефакт

#### Поиск по проекту
- `POST /projects/{project_id}/search` – семантический поиск в рамках проекта

### Глобальная индексация и поиск (новые эндпоинты)

#### Индексация документов завода
```bash
POST /index
Content-Type: application/json

{
  "documents": [
    "BR2/C2.6/C2.6.md",
    "BR2/C2.6/models.py",
    "BR2/C2.6/services.py",
    "BR2/C2.6/main.py"
  ]
}
```

**Ответ:**
```json
{
  "status": "ok",
  "indexed_count": 4,
  "errors": []
}
```

#### Глобальный поиск по заводу
```bash
POST /search
Content-Type: application/json

{
  "query": "как работает индексация",
  "limit": 5
}
```

**Ответ:**
```json
{
  "results": [
    {
      "path": "BR2/C2.6/services.py",
      "score": 0.85,
      "snippet": "def index_document(file_path: str) -> tuple[bool, str]:...",
      "metadata": {
        "filename": "services.py",
        "type": "code",
        "size": 12345,
        "timestamp": "2026-04-05T11:30:00Z"
      }
    }
  ]
}
```

## Тестирование
```bash
pytest -v
```

## Архитектура
- **FastAPI** – веб-фреймворк
- **ChromaDB** – векторная база данных
- **sentence-transformers/all-MiniLM-L6-v2** – модель эмбеддингов
- **SQLite** – реляционное хранилище метаданных
- **httpx** – асинхронные HTTP-клиенты для логирования в BR18