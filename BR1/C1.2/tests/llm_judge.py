"""
Модуль LLM-судьи для оценки качества проектирования веток и контейнеров в C1.2.
Использует DeepSeek API (или C19.2, если доступен) для оценки недетерминированных результатов.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

# Конфигурация
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
LLM_JUDGE_URL = os.getenv("LLM_JUDGE_URL", "https://api.deepseek.com/v1/chat/completions")
C19_2_URL = os.getenv("C19_2_URL", "http://localhost:8119/api/evaluate")  # C19.2 Prompt Optimizer
USE_C19_2_IF_AVAILABLE = os.getenv("USE_C19_2_IF_AVAILABLE", "true").lower() == "true"

# Таймауты
REQUEST_TIMEOUT = 30.0  # секунд
MAX_RETRIES = 2


async def call_llm_judge(
    prompt: str,
    context: Optional[Dict[str, Any]] = None,
    criteria: Optional[str] = None,
    max_score: int = 10
) -> Dict[str, Any]:
    """
    Вызывает LLM-судью для оценки ответа по заданным критериям.
    
    Args:
        prompt: Текст для оценки
        context: Дополнительный контекст (например, исходный запрос)
        criteria: Критерии оценки (если None, используются стандартные)
        max_score: Максимальный балл (по умолчанию 10)
    
    Returns:
        Словарь с результатами оценки:
        {
            "score": float (0-10),
            "passed": bool,
            "comment": str,
            "criteria_breakdown": Dict[str, float],
            "timestamp": str
        }
    """
    if context is None:
        context = {}
    
    if criteria is None:
        criteria = """
        Оцени ответ по следующим критериям (каждый от 0 до 10):
        1. Полнота: ответ содержит всю необходимую информацию
        2. Точность: информация корректна и соответствует запросу
        3. Структурированность: ответ хорошо организован и логичен
        4. Полезность: ответ практичен и применим
        5. Ясность: ответ понятен и не содержит двусмысленностей
        """
    
    # Формируем промпт для судьи
    judge_prompt = f"""
    Ты - эксперт-оценщик качества ответов ИИ. Оцени следующий ответ по заданным критериям.
    
    КОНТЕКСТ ЗАПРОСА:
    {json.dumps(context, ensure_ascii=False, indent=2)}
    
    КРИТЕРИИ ОЦЕНКИ:
    {criteria}
    
    ОТВЕТ ДЛЯ ОЦЕНКИ:
    {prompt}
    
    ИНСТРУКЦИИ:
    1. Оцени каждый критерий от 0 до {max_score}
    2. Рассчитай общий средний балл
    3. Определи, проходит ли ответ (passed = True если средний балл >= 7)
    4. Напиши краткий комментарий с обоснованием оценки
    5. Верни результат в формате JSON:
    {{
        "score": средний_балл,
        "passed": true/false,
        "comment": "твой комментарий",
        "criteria_breakdown": {{
            "полнота": балл,
            "точность": балл,
            "структурированность": балл,
            "полезность": балл,
            "ясность": балл
        }},
        "recommendations": ["рекомендация 1", "рекомендация 2"]
    }}
    
    Только JSON, без дополнительного текста.
    """
    
    # Пытаемся использовать C19.2 если доступен
    if USE_C19_2_IF_AVAILABLE:
        try:
            result = await _call_c19_2_judge(judge_prompt, context)
            if result:
                return result
        except Exception as e:
            print(f"C19.2 judge failed, falling back to DeepSeek: {e}")
    
    # Fallback на DeepSeek
    return await _call_deepseek_judge(judge_prompt, max_score)


async def _call_c19_2_judge(prompt: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Вызывает C19.2 Prompt Optimizer как судью."""
    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
            response = await client.post(
                C19_2_URL,
                json={
                    "prompt": prompt,
                    "context": context,
                    "evaluation_type": "quality_assessment",
                    "max_score": 10
                }
            )
            response.raise_for_status()
            result = response.json()
            
            # Адаптируем формат ответа C19.2 к нашему формату
            if "evaluation" in result:
                eval_data = result["evaluation"]
                return {
                    "score": eval_data.get("score", 0),
                    "passed": eval_data.get("score", 0) >= 7,
                    "comment": eval_data.get("feedback", "Оценка от C19.2"),
                    "criteria_breakdown": eval_data.get("criteria_scores", {}),
                    "timestamp": datetime.now().isoformat(),
                    "judge": "C19.2"
                }
    except Exception as e:
        print(f"Error calling C19.2 judge: {e}")
    
    return None


async def _call_deepseek_judge(prompt: str, max_score: int) -> Dict[str, Any]:
    """Вызывает DeepSeek API как судью."""
    if not DEEPSEEK_API_KEY:
        return {
            "score": 0,
            "passed": False,
            "comment": "DEEPSEEK_API_KEY not set",
            "criteria_breakdown": {},
            "timestamp": datetime.now().isoformat(),
            "judge": "none"
        }
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": "Ты - эксперт-оценщик. Оценивай ответы строго по критериям и возвращай только JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,
        "max_tokens": 1000
    }
    
    for attempt in range(MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                response = await client.post(LLM_JUDGE_URL, headers=headers, json=payload)
                response.raise_for_status()
                
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                
                # Извлекаем JSON из ответа
                try:
                    # Ищем JSON в тексте
                    start = content.find('{')
                    end = content.rfind('}') + 1
                    if start >= 0 and end > start:
                        json_str = content[start:end]
                        result = json.loads(json_str)
                    else:
                        # Если не нашли JSON, создаём fallback результат
                        result = {
                            "score": max_score / 2,  # средний балл
                            "passed": False,
                            "comment": f"Не удалось извлечь JSON из ответа: {content[:100]}...",
                            "criteria_breakdown": {}
                        }
                except json.JSONDecodeError as e:
                    result = {
                        "score": 0,
                        "passed": False,
                        "comment": f"Ошибка парсинга JSON: {e}",
                        "criteria_breakdown": {}
                    }
                
                # Добавляем метаданные
                result["timestamp"] = datetime.now().isoformat()
                result["judge"] = "DeepSeek"
                result["attempt"] = attempt + 1
                
                # Гарантируем наличие всех полей
                if "score" not in result:
                    result["score"] = 0
                if "passed" not in result:
                    result["passed"] = result["score"] >= 7
                if "comment" not in result:
                    result["comment"] = "Оценка выполнена"
                if "criteria_breakdown" not in result:
                    result["criteria_breakdown"] = {}
                if "recommendations" not in result:
                    result["recommendations"] = []
                
                return result
                
        except httpx.TimeoutException:
            if attempt == MAX_RETRIES - 1:
                return {
                    "score": 0,
                    "passed": False,
                    "comment": f"Таймаут после {MAX_RETRIES} попыток",
                    "criteria_breakdown": {},
                    "timestamp": datetime.now().isoformat(),
                    "judge": "DeepSeek"
                }
            await asyncio.sleep(1 * (attempt + 1))  # Экспоненциальная задержка
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return {
                    "score": 0,
                    "passed": False,
                    "comment": f"Ошибка API: {str(e)}",
                    "criteria_breakdown": {},
                    "timestamp": datetime.now().isoformat(),
                    "judge": "DeepSeek"
                }
            await asyncio.sleep(1 * (attempt + 1))


def evaluate_branch_design_quality(branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Специализированная оценка качества проектирования веток.
    
    Args:
        branches: Список веток из C1.2
    
    Returns:
        Результат оценки
    """
    criteria = """
    Оцени проектирование веток по следующим критериям (каждый от 0 до 10):
    1. Количество: оптимальное количество веток (3-5 для среднего проекта)
    2. Полнота: каждая ветка имеет ID, название, описание
    3. Независимость: ветки относительно независимы и могут разрабатываться параллельно
    4. Сложность: сложность веток сбалансирована (нет слишком простых или слишком сложных)
    5. Логичность: ветки логично разделяют функциональность проекта
    6. Приоритизация: есть понимание порядка реализации
    7. Формат ID: ID веток соответствуют формату BRX (например, BR1, BR2)
    """
    
    branches_text = json.dumps(branches, ensure_ascii=False, indent=2)
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        call_llm_judge(branches_text, criteria=criteria, max_score=10)
    )


def evaluate_container_design_quality(containers: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Специализированная оценка качества проектирования контейнеров.
    
    Args:
        containers: Список контейнеров
    
    Returns:
        Результат оценки
    """
    criteria = """
    Оцени проектирование контейнеров по следующим критериям (каждый от 0 до 10):
    1. Специализация: каждый контейнер имеет чёткую специализацию
    2. Полнота: контейнеры имеют ID, название, описание, порты, зависимости
    3. Масштабируемость: контейнеры могут масштабироваться независимо
    4. Связность: зависимости между контейнерами логичны и минимальны
    5. Реализуемость: контейнеры технически реализуемы
    6. Формат ID: ID контейнеров соответствуют формату CX.Y (например, C1.1, C2.3)
    7. Документированность: есть описание назначения и функций
    """
    
    containers_text = json.dumps(containers, ensure_ascii=False, indent=2)
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        call_llm_judge(containers_text, criteria=criteria, max_score=10)
    )


def evaluate_patch_design_quality(patches: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Специализированная оценка качества проектирования патчей.
    
    Args:
        patches: Список патчей
    
    Returns:
        Результат оценки
    """
    criteria = """
    Оцени проектирование патчей по следующим критериям (каждый от 0 до 10):
    1. Конкретность: каждый патч решает конкретную задачу
    2. Полнота: патчи имеют ID, название, описание, контейнеры
    3. Независимость: патчи могут реализовываться относительно независимо
    4. Приоритизация: правильно определён приоритет (high/medium/low)
    5. Оценка сложности: реалистичная оценка сложности (S/M/L/XL)
    6. Формат ID: ID патчей соответствуют формату PX.Y.Z (например, P1.2.3)
    7. Тестируемость: предусмотрены тесты и критерии готовности
    """
    
    patches_text = json.dumps(patches, ensure_ascii=False, indent=2)
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        call_llm_judge(patches_text, criteria=criteria, max_score=10)
    )


def evaluate_decomposition_quality(
    l2_json: Dict[str, Any],
    decomposition_result: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Оценка качества декомпозиции L2 на ветки/контейнеры/патчи.
    
    Args:
        l2_json: Исходный L2
        decomposition_result: Результат декомпозиции
    
    Returns:
        Результат оценки
    """
    criteria = """
    Оцени качество декомпозиции проекта по следующим критериям (каждый от 0 до 10):
    1. Соответствие L2: декомпозиция полностью покрывает требования L2
    2. Глубина: достаточная глубина декомпозиции (ветки → контейнеры → патчи)
    3. Сбалансированность: работа распределена равномерно между компонентами
    4. Практичность: декомпозиция пригодна для реальной реализации
    5. Полнота: все аспекты L2 учтены в декомпозиции
    6. Гибкость: оставлено пространство для изменений и уточнений
    7. Документированность: результат хорошо документирован
    """
    
    context = {
        "original_l2": l2_json,
        "decomposition_result": decomposition_result
    }
    
    evaluation_text = f"""
    ИСХОДНЫЙ L2:
    {json.dumps(l2_json, ensure_ascii=False, indent=2)}
    
    РЕЗУЛЬТАТ ДЕКОМПОЗИЦИИ:
    {json.dumps(decomposition_result, ensure_ascii=False, indent=2)}
    """
    
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        call_llm_judge(evaluation_text, context=context, criteria=criteria, max_score=10)
    )


# Синхронная обёртка для использования в тестах
def call_llm_judge_sync(*args, **kwargs) -> Dict[str, Any]:
    """Синхронная обёртка для call_llm_judge."""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(call_llm_judge(*args, **kwargs))