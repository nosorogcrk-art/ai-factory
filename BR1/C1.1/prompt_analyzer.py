import asyncio
import json
import logging
import httpx
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

PROJECT_MEMORY_URL = "http://project-memory:8108"
PROMPT_OPTIMIZER_URL = "http://prompt-optimizer:8092"  # изменить, если порт другой
SKILL_EXECUTE_URL = "http://skill-integrator:8090/execute"
ANALYSIS_DIR = Path("01_ЦЕХ/МЕТРИКИ/prompt_analysis")
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

async def fetch_dialog_history(project_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    """Получает сообщения проекта из C2.6."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{PROJECT_MEMORY_URL}/projects/{project_id}/messages",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            # C2.6 возвращает массив сообщений напрямую
            if isinstance(data, list):
                return data
            else:
                return data.get("messages", [])
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error fetching dialog for project {project_id}: {e}")
        return []
    except httpx.RequestError as e:
        logger.error(f"Request error fetching dialog for project {project_id}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching dialog for project {project_id}: {e}")
        return []

async def call_dialog_analyzer_skill(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """Вызывает навык dialog_analyzer через C7.4 /execute."""
    context = {"messages": messages}
    payload = {
        "task_type": "dialog_analyzer",
        "context": context
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(SKILL_EXECUTE_URL, json=payload, timeout=60.0)
            resp.raise_for_status()
            data = resp.json()
            result = data.get("result")
            if not result:
                logger.error("No result field in response")
                return {
                    "analysis": "Не удалось получить анализ",
                    "suggestions": [],
                    "risk_level": "unknown"
                }
            return result
    except Exception as e:
        logger.error(f"Failed to call dialog_analyzer skill: {e}")
        return {
            "analysis": "Не удалось получить анализ",
            "suggestions": [],
            "risk_level": "unknown"
        }

async def send_to_prompt_optimizer(skill_id: str, suggestions: List[str]) -> bool:
    """Отправляет предложения в C19.2 (или логирует)."""
    if not suggestions:
        logger.info(f"No suggestions to send for skill {skill_id}")
        return True
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "skill_id": skill_id,
                "suggestions": suggestions,
                "timestamp": datetime.now().isoformat()
            }
            
            response = await client.post(
                f"{PROMPT_OPTIMIZER_URL}/optimize",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                logger.info(f"Sent {len(suggestions)} suggestions to prompt optimizer for skill {skill_id}")
                return True
            else:
                logger.warning(f"Prompt optimizer returned {response.status_code}: {response.text}")
                # Логируем, но не считаем ошибкой
                return False
                
    except httpx.RequestError as e:
        logger.warning(f"Could not connect to prompt optimizer at {PROMPT_OPTIMIZER_URL}: {e}")
        logger.info(f"Suggestions for skill {skill_id} (not sent): {suggestions}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending to prompt optimizer: {e}")
        return False

async def analyze_project_dialog(project_id: str, skill_id: str = "SKILL-DISCOVERY-001") -> Dict[str, Any]:
    """Анализирует диалог проекта, вызывает навык, сохраняет отчёт."""
    logger.info(f"Analyzing dialog for project {project_id}")
    messages = await fetch_dialog_history(project_id)
    if not messages:
        return {"status": "no_messages", "project_id": project_id}
    
    result = await call_dialog_analyzer_skill(messages)
    if result is None:
        result = {
            "analysis": "Не удалось получить анализ",
            "suggestions": [],
            "risk_level": "unknown"
        }
    
    # Сохраняем отчёт (как раньше)
    report_file = ANALYSIS_DIR / f"{project_id}_analysis.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "project_id": project_id,
            "analyzed_at": datetime.now().isoformat(),
            "analysis": result.get("analysis", ""),
            "suggestions": result.get("suggestions", []),
            "risk_level": result.get("risk_level", "unknown")
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Analysis saved to {report_file}")
    
    # Опционально: отправить в C19.2
    if result.get("suggestions"):
        await send_to_prompt_optimizer(skill_id, result["suggestions"])
    
    return result

async def prompt_analysis_scheduler(interval_seconds: int = 86400):
    """Фоновый планировщик, раз в сутки анализирует завершённые проекты."""
    logger.info(f"Prompt analysis scheduler started, interval: {interval_seconds} seconds")
    
    while True:
        try:
            # Ждём указанный интервал
            await asyncio.sleep(interval_seconds)
            
            logger.info("Starting scheduled prompt analysis")
            
            # Получаем список проектов из C2.6
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(f"{PROJECT_MEMORY_URL}/projects")
                    if response.status_code == 200:
                        projects = response.json().get("projects", [])
                        # Фильтруем завершённые проекты
                        completed_projects = [
                            p for p in projects 
                            if p.get("status") in ["completed", "closed", "done"]
                        ]
                        
                        logger.info(f"Found {len(completed_projects)} completed projects for analysis")
                        
                        # Анализируем каждый завершённый проект
                        for project in completed_projects[:10]:  # Ограничиваем 10 проектами за раз
                            project_id = project.get("id")
                            if project_id:
                                try:
                                    await analyze_project_dialog(project_id)
                                    await asyncio.sleep(1)  # Небольшая пауза между проектами
                                except Exception as e:
                                    logger.error(f"Error analyzing project {project_id}: {e}")
                                    continue
                    else:
                        logger.warning(f"Failed to fetch projects: {response.status_code}")
            except Exception as e:
                logger.error(f"Error fetching projects: {e}")
            
            logger.info("Scheduled prompt analysis completed")
            
        except asyncio.CancelledError:
            logger.info("Prompt analysis scheduler cancelled")
            break
        except Exception as e:
            logger.error(f"Error in prompt analysis scheduler: {e}")
            await asyncio.sleep(300)  # Пауза при ошибке