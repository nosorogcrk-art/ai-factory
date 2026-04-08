import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel

from models import AnalyzeRequest, HypothesisRequest, HealthResponse, ApproveRequest, RejectRequest, HintsRequest
from services import CognitiveEngineService
from log_analyzer import scheduler_loop as log_analyzer_scheduler
from semantic_search import provide_hints_for_new_project
from external_search import external_search_scheduler
from prompt_analyzer import prompt_analysis_scheduler, analyze_project_dialog, PROJECT_MEMORY_URL
from decomposition_analyzer import decomposition_analyzer_scheduler, run_decomposition_analysis
from integrator_auditor import integrator_audit_scheduler, run_integrator_audit
from auto_patch_initiator import auto_patch_scheduler, run_auto_patch_initiation

# --- Конфигурация ---
LOG_FILE = Path("01_ЦЕХ/01_ЖУРНАЛЫ/cognitive_engine.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация сервиса
cognitive_service = CognitiveEngineService()

async def scheduler_loop():
    """Фоновая задача для ежедневного анализа"""
    if not cognitive_service.daily_analysis_enabled:
        logger.info("Daily analysis scheduler disabled")
        return
    logger.info(f"Daily analysis scheduler started, will run at {cognitive_service.daily_analysis_hour}:00")
    while True:
        now = datetime.now()
        # Вычисляем время следующего запуска
        next_run = now.replace(hour=cognitive_service.daily_analysis_hour, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        logger.info(f"Next daily analysis at {next_run.isoformat()}, waiting {wait_seconds:.0f} seconds")
        await asyncio.sleep(wait_seconds)
        try:
            await cognitive_service.run_daily_analysis()
        except Exception as e:
            logger.error(f"Scheduled analysis failed: {e}")
            await cognitive_service._send_log_to_br18("daily_analysis_failed", {"error": str(e)})

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запуск при старте
    logger.info("Cognitive Engine (Дедал) запущен")
    # Запуск планировщика ежедневного анализа
    asyncio.create_task(scheduler_loop())
    # Запуск планировщика лог-анализатора (ежедневные отчёты)
    asyncio.create_task(log_analyzer_scheduler(interval_seconds=86400, period_hours=24))
    # Запуск планировщика внешнего поиска (раз в сутки)
    asyncio.create_task(external_search_scheduler(interval_seconds=86400))
    # Запуск планировщика анализа промптов (раз в сутки)
    asyncio.create_task(prompt_analysis_scheduler(interval_seconds=86400))
    # Запуск планировщика анализа декомпозиции (раз в сутки)
    asyncio.create_task(decomposition_analyzer_scheduler(interval_seconds=86400))
    # Запуск планировщика аудита интегратора (раз в сутки)
    asyncio.create_task(integrator_audit_scheduler(interval_seconds=86400))
    # Запуск планировщика автоматических патчей (раз в час)
    asyncio.create_task(auto_patch_scheduler(interval_seconds=3600))
    yield
    # Очистка при завершении
    await cognitive_service.close()
    logger.info("Cognitive Engine (Дедал) остановлен")

app = FastAPI(
    title="Cognitive Engine (Дедал)",
    version="1.0.0",
    description="Мета-агент для анализа логов, генерации гипотез и создания задач",
    lifespan=lifespan
)

# --- API эндпоинты ---

@app.post("/analyze", response_model=dict)
async def analyze_logs(request: AnalyzeRequest):
    """
    Анализирует логи и метрики из BR18 за указанный период.
    Возвращает отчёт о проблемах и гипотезах улучшений.
    """
    try:
        report = await cognitive_service.analyze_logs(
            period_hours=request.period_hours,
            container_filter=request.container_filter
        )
        
        # Логирование в BR18 (заглушка)
        logger.info(f"Анализ выполнен: {report.error_count} ошибок за {request.period_hours} часов")
        
        return {
            "status": "success",
            "report": report.dict(),
            "message": f"Анализ завершён. Найдено {report.error_count} ошибок."
        }
    except Exception as e:
        logger.error(f"Ошибка при анализе: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")

@app.post("/analyze/logs")
async def manual_analyze(period_hours: int = 24):
    from log_analyzer import run_analysis
    report = await run_analysis(period_hours)
    return report

@app.post("/hypothesis", response_model=dict)
async def create_hypothesis(request: HypothesisRequest):
    """
    Принимает гипотезу и создаёт задачу в handover системе (BR7/C7.2).
    """
    try:
        task = await cognitive_service.create_hypothesis_task(
            hypothesis_text=request.hypothesis_text,
            priority=request.priority,
            related_containers=request.related_containers
        )
        
        return {
            "status": "success",
            "task": task.dict(),
            "message": f"Гипотеза создана и задача назначена {task.assigned_to}"
        }
    except Exception as e:
        logger.error(f"Ошибка при создании гипотезы: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка создания гипотезы: {str(e)}")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Healthcheck эндпоинт для проверки работоспособности.
    """
    try:
        health_status = await cognitive_service.get_health_status()
        return HealthResponse(**health_status)
    except Exception as e:
        logger.error(f"Ошибка healthcheck: {e}")
        return HealthResponse(
            status="unhealthy",
            version="1.0.0",
            dependencies={"error": str(e)},
            uptime_seconds=0
        )

@app.get("/hypothesis/{hypothesis_id}", response_model=dict)
async def get_hypothesis(hypothesis_id: str):
    """
    Получает информацию о задаче гипотезы по ID.
    """
    task = await cognitive_service.get_hypothesis_task(hypothesis_id)
    if not task:
        raise HTTPException(status_code=404, detail="Гипотеза не найдена")
    return {"status": "success", "task": task.dict()}

@app.get("/hypothesis", response_model=dict)
async def list_hypotheses(status: Optional[str] = None):
    """
    Список всех задач гипотез с опциональной фильтрацией по статусу.
    """
    tasks = await cognitive_service.list_hypothesis_tasks(status)
    return {
        "status": "success",
        "count": len(tasks),
        "tasks": [task.dict() for task in tasks]
    }

@app.post("/hypothesis/{hypothesis_id}/approve", response_model=dict)
async def approve_hypothesis(hypothesis_id: str, req: ApproveRequest):
    try:
        result = await cognitive_service.approve_hypothesis(hypothesis_id, req.comment)
        return result
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/hypothesis/{hypothesis_id}/reject", response_model=dict)
async def reject_hypothesis(hypothesis_id: str, req: RejectRequest):
    try:
        result = await cognitive_service.reject_hypothesis(hypothesis_id, req.reason)
        return result
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))

@app.post("/generate_hints")
async def generate_hints(req: HintsRequest):
    """Вызывается Аргусом при создании нового проекта."""
    hints = await provide_hints_for_new_project(req.project_id, req.initial_message)
    return {"status": "ok", "hints_count": len(hints)}

class AnalyzePromptRequest(BaseModel):
    project_id: Optional[str] = None

@app.post("/analyze_prompts")
async def manual_analyze_prompts(req: AnalyzePromptRequest):
    """Ручной запуск анализа диалогов проекта."""
    if req.project_id:
        result = await analyze_project_dialog(req.project_id)
        return {"status": "ok", "analysis": result}
    else:
        # Упрощённая реализация для всех проектов
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{PROJECT_MEMORY_URL}/projects")
                if response.status_code == 200:
                    projects = response.json().get("projects", [])
                    results = []
                    for project in projects[:5]:  # Ограничиваем 5 проектами
                        project_id = project.get("id")
                        if project_id:
                            try:
                                result = await analyze_project_dialog(project_id)
                                results.append({"project_id": project_id, "status": "analyzed"})
                                await asyncio.sleep(0.5)
                            except Exception as e:
                                results.append({"project_id": project_id, "status": "error", "error": str(e)})
                    return {"status": "manual_trigger", "message": f"Analyzed {len(results)} projects", "results": results}
                else:
                    return {"status": "error", "message": f"Failed to fetch projects: {response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

@app.post("/collect_external")
async def manual_collect(keywords: List[str] = None):
    from external_search import collect_external_knowledge
    items = await collect_external_knowledge(keywords)
    return {"status": "ok", "items_count": len(items)}

@app.post("/analyze_decomposition")
async def manual_decomposition_analysis():
    """Ручной запуск анализа декомпозиции."""
    result = await run_decomposition_analysis()
    return {"status": "ok", "analysis": result}

@app.post("/audit_integrator")
async def manual_audit(period_days: int = 7):
    """Ручной запуск аудита интегратора."""
    result = await run_integrator_audit(period_days)
    return {"status": "ok", "result": result}

@app.post("/trigger_auto_patches")
async def trigger_auto_patches():
    """Ручной запуск сканирования и создания задач."""
    await run_auto_patch_initiation()
    return {"status": "ok", "message": "Auto patch initiation triggered"}

@app.get("/")
async def root():
    """
    Корневой эндпоинт с информацией о сервисе.
    """
    return {
        "service": "Cognitive Engine (Дедал)",
        "version": "1.0.0",
        "description": "Мета-агент для анализа системы и генерации гипотез улучшений",
        "endpoints": {
            "POST /analyze": "Анализ логов и метрик",
            "POST /hypothesis": "Создание гипотезы и задачи",
            "GET /health": "Healthcheck",
            "GET /hypothesis": "Список гипотез",
            "GET /hypothesis/{id}": "Получение гипотезы по ID",
            "POST /hypothesis/{id}/approve": "Утверждение гипотезы",
            "POST /hypothesis/{id}/reject": "Отклонение гипотезы",
            "POST /generate_hints": "Генерация подсказок для нового проекта",
            "POST /collect_external": "Ручной запуск сбора внешних знаний",
            "POST /analyze_prompts": "Анализ диалогов проекта для улучшения промптов",
            "POST /analyze_decomposition": "Анализ декомпозиции патчей и генерация правил",
            "POST /audit_integrator": "Аудит интегратора через навык integrator_audit",
            "POST /trigger_auto_patches": "Ручной запуск инициатора автоматических патчей"
        }
    }
