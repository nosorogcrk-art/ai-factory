# Ошибки сквозного теста итерации 30

**Дата:** 2026-04-11
**Тестировщик:** Cline

## 0. Проверка портов (Шаг 0)
```bash
grep -E '"[0-9]+:[0-9]+"' docker-compose.yml | sed 's/.*"\([0-9]*\):[0-9]*".*/\1/' | sort -n | uniq -d
```
**Вывод:** (пустая строка) - конфликтов портов нет.

## 1. Контейнеры, которые не работали или не были запущены
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```
**Вывод:**
```
NAMES                           STATUS
ai-factory-dialogue-manager-1   Up 3 hours (healthy)
ai-factory-patch-architect-1    Up 4 hours (healthy)
ai-factory-integrator-1         Up 5 hours (healthy)
ai-factory-handover-1           Up 5 hours (healthy)
ai-factory-dialogue-console-1   Up 7 hours (healthy)
ai-factory-project-memory-1     Up 11 hours (healthy)
ai-factory-indexer-1            Up 20 hours (unhealthy)
ai-factory-skill-integrator-1   Up 21 hours (healthy)
ai-factory-system-mapper-1      Up 21 hours (healthy)
ai-factory-ab-tester-1          Up 31 hours (healthy)
```

**Проблемы:**
- Контейнер `ai-factory-packager-1` не запущен (C10.3 Packager отсутствует)
- Контейнер `ai-factory-indexer-1` запущен, но имеет статус `unhealthy`
- Контейнеры `log-aggregator` и `cognitive-engine` недоступны (ошибки подключения в логах Handover)


## 2. Ошибки в диалоге (C9.4)
- Ошибок не выявлено. Диалог прошёл успешно:

**Создание проекта:**
```bash
curl -s -X POST "http://localhost:8108/projects" -H "Content-Type: application/json" -d '{"name": "HelloWorldTest", "description": "Тестовый проект для сквозного теста итерации 30"}' | jq .
```
**Вывод:**
```json
{
  "id": "proj_790bfb96",
  "name": "HelloWorldTest",
  "description": "Тестовый проект для сквозного теста итерации 30",
  "status": "active",
  "created_at": "2026-04-11T00:06:37.235680+00:00",
  "updated_at": "2026-04-11T00:06:37.235680+00:00"
}
```

**Текстовая копия диалога (все сообщения):**

**Пользователь → Ассистент:**
1. "Хочу создать простой REST API, который по GET запросу на /hello возвращает JSON {\"message\": \"Hello, World!\"}"
2. "Python 3.12, FastAPI"
3. "Не нужна база данных, только один эндпоинт"
4. "Успех – когда при обращении к /hello получаю приветствие"
5. "Проект успешен, когда GET запрос к /hello возвращает JSON с сообщением Hello, World! и статус код 200. Это простой тестовый API для демонстрации работы системы."

**Ассистент → Пользователь:**
1. "В чём сейчас сложность?"
2. "Кто будет основными пользователями приложения?"
3. "Какие 3–5 самых важных действий должно выполнять приложение?"
4. "Как мы поймём, что проект успешен?"
5. "✅ Проект сформирован, передан архитектору."

**Выводы curl запросов к Project Memory:**

```bash
curl -s "http://localhost:8108/projects" | jq .
```
**Вывод (сокращённо, показаны первые 3 проекта из 50+):**
```json
[
  {
    "id": "proj_790bfb96",
    "name": "HelloWorldTest",
    "description": "Тестовый проект для сквозного теста итерации 30",
    "status": "active",
    "created_at": "2026-04-11T00:06:37.235680+00:00",
    "updated_at": "2026-04-11T00:06:37.235680+00:00"
  },
  {
    "id": "proj_1fcfb200",
    "name": "test_availability_1775863386",
    "description": null,
    "status": "active",
    "created_at": "2026-04-10T23:23:06.353119+00:00",
    "updated_at": "2026-04-10T23:23:06.353119+00:00"
  },
  {
    "id": "proj_35c14f6c",
    "name": "E2E Test Dialog 1775863385",
    "description": null,
    "status": "active",
    "created_at": "2026-04-10T23:23:05.803488+00:00",
    "updated_at": "2026-04-10T23:23:05.803488+00:00"
  },
  ... (ещё 47 проектов)
]
```

```bash
curl -s "http://localhost:8108/projects/proj_790bfb96/messages" | jq .
```
**Вывод (полный список из 12 сообщений):**
```json
[
  {
    "id": 154,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Начинаем опрос для нового проекта «HelloWorldTest». Пожалуйста, опишите задачу.",
    "timestamp": "2026-04-11T00:06:38.610514+00:00",
    "message_type": "text"
  },
  {
    "id": 155,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "Какую главную проблему вы хотите решить с помощью этого приложения?",
    "timestamp": "2026-04-11T00:06:40.766672+00:00",
    "message_type": "text"
  },
  {
    "id": 156,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Хочу создать простой REST API, который по GET запросу на /hello возвращает JSON {\"message\": \"Hello, World!\"}",
    "timestamp": "2026-04-11T00:07:06.624646+00:00",
    "message_type": "text"
  },
  {
    "id": 157,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "В чём сейчас сложность?",
    "timestamp": "2026-04-11T00:07:08.418795+00:00",
    "message_type": "text"
  },
  {
    "id": 158,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Python 3.12, FastAPI",
    "timestamp": "2026-04-11T00:07:18.318721+00:00",
    "message_type": "text"
  },
  {
    "id": 159,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "Кто будет основными пользователями приложения?",
    "timestamp": "2026-04-11T00:07:20.209229+00:00",
    "message_type": "text"
  },
  {
    "id": 160,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Не нужна база данных, только один эндпоинт",
    "timestamp": "2026-04-11T00:07:29.081861+00:00",
    "message_type": "text"
  },
  {
    "id": 161,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "Какие 3–5 самых важных действий должно выполнять приложение?",
    "timestamp": "2026-04-11T00:07:30.861365+00:00",
    "message_type": "text"
  },
  {
    "id": 162,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Успех – когда при обращении к /hello получаю приветствие",
    "timestamp": "2026-04-11T00:07:40.086971+00:00",
    "message_type": "text"
  },
  {
    "id": 163,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "Как мы поймём, что проект успешен?",
    "timestamp": "2026-04-11T00:07:42.016893+00:00",
    "message_type": "text"
  },
  {
    "id": 164,
    "project_id": "proj_790bfb96",
    "role": "user",
    "content": "Проект успешен, когда GET запрос к /hello возвращает JSON с сообщением Hello, World! и статус код 200. Это простой тестовый API для демонстрации работы системы.",
    "timestamp": "2026-04-11T00:07:52.255264+00:00",
    "message_type": "text"
  },
  {
    "id": 165,
    "project_id": "proj_790bfb96",
    "role": "assistant",
    "content": "✅ Проект сформирован, передан архитектору.",
    "timestamp": "2026-04-11T00:08:09.202222+00:00",
    "message_type": "text"
  }
]
```

```bash
curl -s "http://localhost:8108/projects/proj_790bfb96/artifacts" | jq .
```
**Вывод:**
```json
[
  {
    "id": "art_734516da",
    "project_id": "proj_790bfb96",
    "artifact_type": "specification",
    "name": "L2_specification",
    "version": "1.0",
    "created_at": "2026-04-11T00:07:57.928279+00:00"
  }
]
```

**L2 спецификация сгенерирована:** `art_734516da`
**Финальный ответ:** "✅ Проект сформирован, передан архитектору."



## 3. Ошибки при сохранении L2 или вызове C1.2
- Ошибок не выявлено. L2 успешно сохранён в project-memory:
  ```json
  {
    "title": "HelloWorldTest REST API",
    "description": "Разработка простого REST API на Python 3.12 с использованием FastAPI...",
    "requirements": ["GET /hello возвращает JSON {\"message\": \"Hello, World!\"}", ...],
    "technical_specs": {...},
    "deliverable": "code",
    "priority": "high",
    "tags": ["API", "demo", "FastAPI", "Python"]
  }
  ```
- Вызов C1.2 выполнен: в логах C9.4 видно "DEBUG _process_l2_response: C1.2 called, patches count: 0"

## 4. Ошибки проектирования (C1.2)
- **Критическая ошибка**: C1.2 вернул пустой результат (patches count: 0)
- В логах C1.2 видно POST запросы к `/decompose` с кодами 200 и 400
- Файл очереди патчей `01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json` существует, но пустой:
  ```json
  {
    "branches": [],
    "containers": [],
    "patches": [],
    "queue": []
  }
  ```

## 5. Ошибки очереди и Handover (C7.2)
- Handover обнаружил новый проект и создал задачу
- **Ошибка**: Нет вызовов `/build_from_queue` к C10.1 (Integrator)
- В логах Handover есть ошибки подключения к `log-aggregator` и `cognitive-engine`, но это не критично для основного потока

## 6. Ошибки генерации кода (C10.1)
- **Ошибка**: C10.1 не вызывался (нет запросов `/build_from_queue`)
- В логах C10.1 только healthcheck запросы
- Директория `01_ЦЕХ/ГЕНЕРАЦИЯ/` не существует

## 7. Ошибки упаковки (C10.3)
- **Критическая ошибка**: Контейнер C10.3 Packager не запущен
- Директория `01_ЦЕХ/ПРОДУКТЫ/` не существует

## 8. Другие проблемы (недоступные сервисы, неправильные порты, отсутствие healthcheck)
- Сервис `log-aggregator:8093` недоступен (ошибки NameResolutionError)
- Сервис `cognitive-engine:8103` недоступен (ошибки NameResolutionError)
- Контейнер `ai-factory-indexer-1` в состоянии `unhealthy`
- Контейнер `ai-factory-packager-1` отсутствует в списке запущенных контейнеров

## 9. Итог: достигнут ли хотя бы частичный успех (например, получен архив)?
- **Частичный успех**: Достигнуты первые 3 этапа из 6:
  1. ✅ Диалог (C9.4) - успешно
  2. ✅ L2 спецификация - успешно создана и сохранена
  3. ✅ Вызов C1.2 - успешно выполнен
  4. ❌ Проектирование (C1.2) - провалено (пустой результат)
  5. ❌ Генерация кода (C10.1) - не запускалась
  6. ❌ Упаковка (C10.3) - сервис не запущен

- **Архив не создан**: Директории `01_ЦЕХ/ГЕНЕРАЦИЯ/` и `01_ЦЕХ/ПРОДУКТЫ/` не существуют
- **Основная проблема**: C1.2 не смог разложить простую задачу на патчи, что остановило весь последующий поток

## 10. Рекомендации по исправлению
1. **Исправить C1.2 (patch-architect)**: Убедиться, что он может обрабатывать простые задачи типа "Hello World API"
2. **Запустить C10.3 (packager)**: Добавить контейнер в docker-compose.yml и запустить
3. **Проверить интеграцию C7.2 → C10.1**: Убедиться, что Handover вызывает `/build_from_queue` при появлении патчей в очереди
4. **Восстановить вспомогательные сервисы**: `log-aggregator` и `cognitive-engine` (не критично для основного потока, но улучшит мониторинг)