#!/bin/bash
# Скрипт для индексации всех артефактов завода в C2.6

BASE_DIR="/Users/a1/Dev/ЗАВОД_АГЕНТОВ/ai-factory"
C2_6_URL="http://localhost:8108/index"
ALL_FILES="/tmp/all_files.txt"

echo "Начинаем индексацию артефактов завода..."
echo "Всего файлов для индексации: $(wc -l < $ALL_FILES)"

# Создаем временный файл с абсолютными путями
ABS_FILES="/tmp/abs_files.txt"
rm -f "$ABS_FILES"
while read -r file; do
    echo "$BASE_DIR/$file" >> "$ABS_FILES"
done < "$ALL_FILES"

# Разбиваем на порции по 20 файлов
BATCH_SIZE=20
TOTAL_FILES=$(wc -l < "$ABS_FILES")
BATCHES=$(( (TOTAL_FILES + BATCH_SIZE - 1) / BATCH_SIZE ))

INDEXED_COUNT=0
ERROR_COUNT=0

for ((i=0; i<BATCHES; i++)); do
    START=$((i * BATCH_SIZE + 1))
    END=$(( (i + 1) * BATCH_SIZE ))
    
    # Получаем порцию файлов
    BATCH_FILES=$(sed -n "${START},${END}p" "$ABS_FILES" | tr '\n' ',' | sed 's/,$//')
    
    # Создаем JSON
    JSON_DATA="{\"documents\": [$(echo "$BATCH_FILES" | sed 's/,/","/g' | sed 's/^/"/' | sed 's/$/"/')]}"
    
    echo "Порция $((i+1))/$BATCHES: файлы $START-$END (из $TOTAL_FILES)"
    
    # Отправляем запрос
    RESPONSE=$(curl -s -X POST "$C2_6_URL" \
        -H "Content-Type: application/json" \
        -d "$JSON_DATA" \
        --max-time 30)
    
    # Парсим ответ
    STATUS=$(echo "$RESPONSE" | grep -o '"status":"[^"]*"' | cut -d'"' -f4)
    COUNT=$(echo "$RESPONSE" | grep -o '"indexed_count":[0-9]*' | cut -d':' -f2)
    ERRORS=$(echo "$RESPONSE" | grep -o '"errors":\[[^]]*\]')
    
    if [ "$STATUS" = "ok" ]; then
        echo "  ✓ Успешно проиндексировано: $COUNT документов"
        INDEXED_COUNT=$((INDEXED_COUNT + COUNT))
    else
        echo "  ✗ Ошибка: $RESPONSE"
        ERROR_COUNT=$((ERROR_COUNT + 1))
    fi
    
    # Небольшая пауза между запросами
    sleep 0.5
done

echo ""
echo "========================================"
echo "ИНДЕКСАЦИЯ ЗАВЕРШЕНА"
echo "Всего файлов: $TOTAL_FILES"
echo "Успешно проиндексировано: $INDEXED_COUNT"
echo "Ошибок при индексации: $ERROR_COUNT"
echo "========================================"

# Проверяем поиск
echo ""
echo "Проверяем поиск в глобальной памяти..."
SEARCH_RESPONSE=$(curl -s -X POST "http://localhost:8108/search" \
    -H "Content-Type: application/json" \
    -d '{"query": "C2.6", "limit": 5}')
    
echo "Результаты поиска по запросу 'C2.6':"
echo "$SEARCH_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SEARCH_RESPONSE"