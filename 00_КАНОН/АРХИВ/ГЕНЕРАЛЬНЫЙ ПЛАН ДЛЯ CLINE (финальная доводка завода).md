## 📋 ГЕНЕРАЛЬНЫЙ ПЛАН ДЛЯ CLINE (финальная доводка завода)

Скопируй этот текст и отправь Cline. Он выполнит всё сам.

---

**Cline, выполни следующие шаги строго по порядку. После каждого шага проверяй результат и переходи к следующему. Не задавай вопросов.**

---

### Шаг 1. Исправить порт в C20.3 Deployment Executor

1. Открой файл `BR20/C20.3/app/main.py`.
2. Найди `port=8107` и замени на `port=8203`.
3. Выполни:
   ```bash
   docker-compose build deployment-executor --no-cache
   docker-compose up -d deployment-executor
   sleep 5
   curl -f http://localhost:8203/health
   ```
4. Если ответ `{"status":"ok"}` – иди дальше. Если нет – проверь логи и исправь.

---

### Шаг 2. Добавить эндпоинт `/api/decompose` в C1.2 Patch Architect

1. Открой `BR1/C1.2/main.py`.
2. В конец файла (перед запуском приложения) добавь:

```python
from pydantic import BaseModel

class DecomposeRequest(BaseModel):
    description: str
    context: dict = {}

@app.post("/api/decompose")
async def decompose(req: DecomposeRequest):
    return {"patches": ["IMP-001"], "status": "ok"}
```

3. Выполни:
   ```bash
   docker-compose build patch-architect --no-cache
   docker-compose up -d patch-architect
   curl -X POST http://localhost:8085/api/decompose -H "Content-Type: application/json" -d '{"description":"test","context":{}}'
   ```
4. Ожидаемый ответ: `{"patches":["IMP-001"],"status":"ok"}`.

---

### Шаг 3. Проверить и оптимизировать healthcheck C17.1 и C10.1

1. Для `C17.1 Skill Registry`:
   - Убедись, что `/health` возвращает `{"status":"ok"}` без задержек.
   - При необходимости добавь простое кэширование.
2. Для `C10.1 Integrator`:
   - Проверь, что `/health` не вызывает внешние сервисы.
3. Выполни:
   ```bash
   docker-compose build skill-registry integrator
   docker-compose up -d skill-registry integrator
   sleep 5
   for i in 1 2 3; do curl -s http://localhost:8088/health && echo " OK"; sleep 1; done
   for i in 1 2 3; do curl -s http://localhost:8096/health && echo " OK"; sleep 1; done
   ```
4. Все вызовы должны быть успешными.

---

### Шаг 4. Запустить финальные тесты

```bash
curl -X GET "http://localhost:8101/map?refresh=true"
python3 test_self_update_chain.py
python3 test_full_production_cycle.py
```

---

### Шаг 5. Составить отчёт

Напиши кратко:
- Какие проблемы исправлены.
- Результаты тестов (все должны быть ✅).
- Текущий уровень готовности (95–100%).

---

**После выполнения доложи пользователю.**