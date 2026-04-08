"""
Модуль LLM-судьи для оценки качества ответов в E2E-тестах.
Использует DeepSeek API (или C19.2, если доступен) для оценки недетерминированных результатов.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional
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


def evaluate_l2_quality(l2_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Специализированная оценка качества L2 (технического задания).
    
    Args:
        l2_json: JSON L2 для оценки
    
    Returns:
        Результат оценки с дополнительными критериями для L2
    """
    criteria = """
    Оцени L2 (техническое задание) по следующим критериям (каждый от 0 до 10):
    1. Полнота: содержит все необходимые разделы (title, description, requirements, technical_specs, deliverable, priority, tags)
    2. Конкретность: требования и спецификации чёткие и измеримые
    3. Реализуемость: проект технически реализуем с указанными технологиями
    4. Структурированность: информация хорошо организована и логична
    5. Ясность: формулировки понятны и не допускают двусмысленностей
    6. Приоритизация: правильно определён приоритет (high/medium/low)
    7. Теги: релевантные теги для классификации
    """
    
    # Преобразуем L2 в текст для оценки
    l2_text = json.dumps(l2_json, ensure_ascii=False, indent=2)
    
    # Используем асинхронный вызов через asyncio.run если не в асинхронном контексте
    try:
        import asyncio
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(
        call_llm_judge(l2_text, criteria=criteria, max_score=10)
    )


def evaluate_branch_design(branches: list) -> Dict[str, Any]:
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