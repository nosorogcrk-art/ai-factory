#!/bin/bash

echo "=== 0. Проверка портов ==="
grep -E '"[0-9]+:[0-9]+"' docker-compose.yml | sed 's/.*"\([0-9]*\):[0-9]*".*/\1/' | sort -n | uniq -d
echo ""

echo "=== 1. docker ps ==="
docker ps --format "table {{.Names}}\t{{.Status}}"
echo ""

echo "=== 2. ID проекта и подтверждение L2 ==="
echo "PROJECT_ID=proj_4e46ba98"
curl -s "http://localhost:8108/projects/proj_4e46ba98/artifacts" | jq '.[] | select(.artifact_type=="specification")'
echo ""

echo "=== 3. Содержимое очереди патчей ==="
cat 01_ЦЕХ/ОЧЕРЕДЬ_ПАТЧЕЙ/latest_queue.json | jq '.queue'
echo ""

echo "=== 4. Логи Handover (вызов /build) ==="
docker logs ai-factory-handover-1 --tail 200 2>&1 | grep -E "integrator|build|200" | tail -20
echo ""

echo "=== 5. Логи интегратора ==="
docker logs ai-factory-integrator-1 --tail 50 2>&1 | grep -i "generate\|files"
echo ""

echo "=== 6. Список архивов и содержимое свежего архива ==="
ls -la 01_ЦЕХ/ПРОДУКТЫ/
NEWEST_ARCHIVE=$(ls -t 01_ЦЕХ/ПРОДУКТЫ/*.zip 2>/dev/null | head -1)
if [ -n "$NEWEST_ARCHIVE" ]; then 
    echo "Самый свежий архив: $NEWEST_ARCHIVE"
    unzip -l "$NEWEST_ARCHIVE"
else 
    echo "No archive found"
fi
echo ""

echo "=== 7. Файл ITERATION_39_ERRORS.md ==="
cat 01_ЦЕХ/ПРОТОКОЛЫ/ITERATION_39_ERRORS.md