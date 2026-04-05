#!/bin/bash
set -e

echo "========================================="
echo "  ЭТАП 10 – Финальное тестирование ядра"
echo "========================================="

# 1. Reality Check
echo -e "\n1. Reality Check (C0.2)"
python3 BR0/C0.2/scanner.py

# 2. Traceability Gate
echo -e "\n2. Traceability Gate (C3.4)"
python3 BR3/C3.4/citations_agent.py TEST-001

# 3. Skill Validation Gate
echo -e "\n3. Skill Validation Gate"
# Создаём тестовый навык, если его нет
curl -s -X POST http://localhost:8088/skills \
  -H "Content-Type: application/json" \
  -d '{"id":"SKILL-TEST-001","name":"Test Skill","version":"1.0.0","description":"Test","status":"active","metadata":{}}' > /dev/null || echo "Skill already exists"

echo "Проверка навыка через интегратор (C10.1):"
curl -s "http://localhost:8096/skills/SKILL-TEST-001/check?run_tests=true"

# 4. Cost/Meaning Counter
echo -e "\n4. Cost Tracker (C18.5)"
curl -s http://localhost:8110/costs || echo "Cost Tracker not running (expected)"

# 5. Сквозной сценарий
echo -e "\n5. Сквозной сценарий"
echo "Запуск оптимизации промпта (C1.1 → C19.2):"
curl -s -X POST http://localhost:8103/cognitive/optimize \
  -H "Content-Type: application/json" \
  -d '{"prompt_id":"argus_v1","goals":["improve_handover"],"num_variants":1}'

echo -e "\nЗапуск сборки (C10.1):"
curl -s -X POST http://localhost:8096/build \
  -H "Content-Type: application/json" \
  -d '{"patch_ids":["TEST-001"],"check_skills":true,"run_tests":true}'

echo -e "\nЗапуск CI/CD (C3.2 → C20.2):"
curl -s -X POST http://localhost:8107/deploy \
  -H "Content-Type: application/json" \
  -d '{"type":"prompt","object_id":"argus_v1","version":"v1.2.5"}'

echo -e "\n========================================="
echo "  Тестирование завершено"
echo "========================================="
