# Skill Graph (C17.3)

Построение графа зависимостей навыков на основе данных из C17.1.

## API

- `GET /health` – проверка здоровья
- `GET /graph` – полный граф (узлы и рёбра)
- `GET /graph/{skill_id}` – информация о навыке и его прямые зависимости
- `GET /dependencies/{skill_id}?transitive=true` – список зависимостей (прямые или транзитивные)
- `GET /reverse-dependencies/{skill_id}` – список навыков, зависящих от данного
- `GET /cycle-check` – проверка наличия циклов в графе

## Переменные окружения

- `SKILL_REGISTRY_URL` – URL реестра навыков (по умолчанию `http://skill-registry:8088`)
- `UPDATE_INTERVAL` – интервал обновления графа (секунды, по умолчанию 3600)
- `BR18_URL` – URL лог-агрегатора
- `ENABLE_BR18` – включить отправку логов (true/false)

## Запуск

```bash
docker-compose up -d skill-graph
Тестирование
bash
pytest tests/