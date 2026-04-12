#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_integrator.py – интегратор навыков.
Читает навыки из файловой системы (00_КАНОН/НАВЫКИ/{task_type}/) и возвращает их содержимое.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

import httpx
from fastapi import FastAPI, HTTPException
from models import CompileRequest, CompileResponse, ExecuteRequest, ExecuteResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Skill Integrator", version="1.1.0")

# Базовый путь к навыкам внутри контейнера
SKILLS_BASE_PATH = Path("/app/00_КАНОН/НАВЫКИ")

# Переменная окружения для API-ключа DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"


def load_skill(task_type: str) -> Dict[str, Any]:
    """
    Загружает навык для указанного типа задачи.
    Возвращает словарь с полями:
      - id: идентификатор навыка из skill.json
      - prompt: содержимое prompt.md
      - skill_data: полные данные из skill.json
    Если навык не найден, возвращает пустой словарь.
    """
    skill_dir = SKILLS_BASE_PATH / task_type
    skill_json_path = skill_dir / "skill.json"
    prompt_md_path = skill_dir / "prompt.md"
    
    if not skill_json_path.exists() or not prompt_md_path.exists():
        logger.warning(f"Skill files not found for task_type={task_type}")
        return {}
    
    try:
        # Читаем skill.json
        with open(skill_json_path, 'r', encoding='utf-8') as f:
            skill_data = json.load(f)
        
        # Читаем prompt.md
        with open(prompt_md_path, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        
        skill_id = skill_data.get('id', f'UNKNOWN-{task_type}')
        
        logger.info(f"Skill {skill_id} loaded for task_type {task_type}")
        return {
            'id': skill_id,
            'prompt': prompt_content,
            'skill_data': skill_data
        }
    except Exception as e:
        logger.error(f"Error loading skill for task_type={task_type}: {e}")
        return {}


def _load_skill_prompt(task_type: str) -> Optional[str]:
    """
    Загружает промпт навыка из файловой системы.
    Возвращает содержимое prompt.md или None, если навык не найден.
    """
    skill_dir = SKILLS_BASE_PATH / task_type
    prompt_md_path = skill_dir / "prompt.md"
    
    if not prompt_md_path.exists():
        logger.warning(f"Skill prompt not found for task_type={task_type}")
        return None
    
    try:
        with open(prompt_md_path, 'r', encoding='utf-8') as f:
            prompt_content = f.read()
        logger.info(f"Skill prompt loaded for task_type={task_type}")
        return prompt_content
    except Exception as e:
        logger.error(f"Error loading skill prompt for task_type={task_type}: {e}")
        return None


async def _call_deepseek(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """
    Вызывает DeepSeek API с системным и пользовательским промптом.
    Возвращает распарсенный JSON-ответ или None при ошибке.
    Очищает ответ от маркеров Markdown (```json).
    Добавлены повторные попытки и улучшенное логирование.
    """
    if not DEEPSEEK_API_KEY:
        logger.error("DEEPSEEK_API_KEY environment variable is not set")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,
        "max_tokens": 4000
    }
    
    max_retries = 3
    retry_delay = 2  # секунды
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling DeepSeek API (attempt {attempt + 1}/{max_retries})")
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(DEEPSEEK_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                
                result = response.json()  # httpx response.json() is synchronous
                logger.debug(f"DeepSeek API raw response: {result}")
                
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                if not content:
                    logger.error("Empty response from DeepSeek API")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    return None
                
                # Очистка от маркеров Markdown
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                # Пытаемся распарсить JSON из ответа
                try:
                    parsed = json.loads(content)
                    logger.info("DeepSeek API call successful, JSON parsed")
                    return parsed
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from DeepSeek response: {e}")
                    logger.debug(f"Response content that failed to parse: {content}")
                    # Если не JSON, возвращаем как текст
                    return {"text": content}
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling DeepSeek API (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling DeepSeek API (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
                continue
            return None
    
    logger.error(f"All {max_retries} attempts to call DeepSeek API failed")
    return None


@app.post("/compile", response_model=CompileResponse)
async def compile_prompt(req: CompileRequest) -> CompileResponse:
    """
    Обрабатывает запрос на компиляцию промпта.
    Для task_type="discovery" загружает реальный навык из файловой системы.
    Для других типов возвращает заглушку.
    """
    logger.info(f"Compile request: {req.dict()}")
    
    # Если указаны конкретные навыки - пока возвращаем заглушку
    if req.required_skills:
        logger.warning(f"Explicit required_skills not yet implemented: {req.required_skills}")
        used_skills = req.required_skills[:req.limit]
        prompt_lines = ["[STUB] Explicit skill selection not yet implemented."]
        for skill_id in used_skills:
            prompt_lines.append(f"- Instruction from {skill_id}: stub content")
        prompt = "\n".join(prompt_lines)
        
        return CompileResponse(
            prompt=prompt,
            used_skills=used_skills,
            warnings=["Explicit skill selection is a stub"],
            total_matched=len(used_skills),
            returned=len(used_skills)
        )
    
    # Обработка по task_type
    if req.task_type == "discovery":
        skill = load_skill(req.task_type)
        if skill:
            return CompileResponse(
                prompt=skill['prompt'],
                used_skills=[skill['id']],
                warnings=[],
                total_matched=1,
                returned=1
            )
        else:
            logger.error(f"Skill discovery not found for task_type={req.task_type}")
            return CompileResponse(
                prompt="",
                used_skills=[],
                warnings=["Skill discovery not found"],
                total_matched=0,
                returned=0
            )
    else:
        # Для других типов - заглушка
        logger.info(f"Task type '{req.task_type}' not implemented, returning stub")
        used_skills = [f"SKILL-{req.task_type.upper()}"]
        prompt = f"[STUB] Skill for task_type '{req.task_type}' is not yet implemented."
        
        return CompileResponse(
            prompt=prompt,
            used_skills=used_skills,
            warnings=[f"Skill for task_type '{req.task_type}' not implemented"],
            total_matched=1,
            returned=1
        )


@app.post("/execute", response_model=ExecuteResponse)
async def execute_skill(req: ExecuteRequest):
    """
    Выполняет навык: загружает промпт навыка, вызывает DeepSeek с контекстом,
    возвращает структурированный JSON-ответ.
    """
    logger.info(f"Execute request for task_type: {req.task_type}")
    
    # 1. Загрузить промпт навыка
    skill_prompt = _load_skill_prompt(req.task_type)
    if not skill_prompt:
        logger.error(f"Skill '{req.task_type}' not found")
        raise HTTPException(status_code=404, detail=f"Skill '{req.task_type}' not found")
    
    # 2. Подготовить пользовательский промпт (JSON из context)
    user_prompt = json.dumps(req.context, ensure_ascii=False)
    
    # 3. Вызвать DeepSeek
    llm_response = await _call_deepseek(skill_prompt, user_prompt)
    if llm_response is None:
        logger.error(f"LLM call failed for task_type={req.task_type}")
        raise HTTPException(status_code=502, detail="LLM call failed")
    
    # 4. Определить skill_id (можно из skill.json)
    skill_id = "unknown"
    try:
        skill_dir = SKILLS_BASE_PATH / req.task_type
        skill_json_path = skill_dir / "skill.json"
        if skill_json_path.exists():
            with open(skill_json_path, 'r', encoding='utf-8') as f:
                skill_meta = json.load(f)
                skill_id = skill_meta.get("id", "unknown")
    except Exception as e:
        logger.warning(f"Could not read skill.json for {req.task_type}: {e}")
    
    logger.info(f"Executed skill {req.task_type} (skill_id: {skill_id})")
    return ExecuteResponse(result=llm_response, skill_id=skill_id, warnings=[])


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
