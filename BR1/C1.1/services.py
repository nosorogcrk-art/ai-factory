import logging
import os
import time
import uuid
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx

from models import AnalysisReport, HypothesisTask, ExternalArticle


logger = logging.getLogger(__name__)


class CognitiveEngineService:
    """Сервис когнитивного движка (Дедал)"""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.handover_url = os.getenv("HANDOVER_URL", "http://handover:8080")
        self.project_memory_url = os.getenv("PROJECT_MEMORY_URL", "http://project-memory:8090")
        self.br18_logs_url = "http://logs:8093/api/logs"  # BR18/C18.1
        self.br18_metrics_url = "http://metrics:8094/api/metrics"  # BR18/C18.2
        self.client = httpx.AsyncClient(timeout=10.0)
        self.hypothesis_tasks: Dict[str, HypothesisTask] = {}
        
        # Переменные для ежедневного анализа
        self.daily_analysis_hour = int(os.getenv("DAILY_ANALYSIS_HOUR", "8"))
        self.daily_analysis_enabled = os.getenv("DAILY_ANALYSIS_ENABLED", "true").lower() == "true"
        self.reports_dir = Path(os.getenv("REPORTS_DIR", "01_ЦЕХ/МЕТРИКИ/daedalus_reports"))
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Переменные для учёта отчётов Ревы (C6.2)
        self.reva_reports_path = Path(os.getenv("REVA_REPORTS_PATH", "01_ЦЕХ/01_ЖУРНАЛЫ/reva_reports.json"))
        self.use_reva_stub = os.getenv("USE_REVA_STUB", "true").lower() == "true"
        self.reva_reports_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Переменные для GitHub API
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.github_api_enabled = os.getenv("GITHUB_API_ENABLED", "true").lower() == "true"
        
        # Переменные для внешних источников знаний (RSS и arXiv)
        self.rss_feeds = json.loads(os.getenv("RSS_FEEDS", '[{"url":"https://habr.com/ru/rss/hub/python/all/","name":"Habr Python"},{"url":"https://medium.com/feed/tag/ai","name":"Medium AI"}]'))
        self.arxiv_enabled = os.getenv("ARXIV_ENABLED", "true").lower() == "true"
        self.arxiv_categories = os.getenv("ARXIV_CATEGORIES", "cs.AI,cs.SE,cs.LG").split(",")
        self.external_cache_file = Path(os.getenv("EXTERNAL_CACHE_FILE", "01_ЦЕХ/МЕТРИКИ/external_cache.json"))
        self.external_cache_file.parent.mkdir(parents=True, exist_ok=True)
        
    async def analyze_logs(self, period_hours: int = 24, container_filter: Optional[str] = None) -> AnalysisReport:
        """
        Анализирует логи и метрики из BR18.
        Пока заглушка, но с правильной архитектурой для расширения.
        """
        start_time = time.time()
        
        # В реальной реализации здесь будет запрос к BR18 API
        # Сейчас используем заглушку с имитацией данных
        
        period_end = datetime.now()
        period_start = period_end - timedelta(hours=period_hours)
        
        # Имитация данных анализа
        error_types = {
            "timeout": 15,
            "connection_error": 8,
            "validation_error": 3,
            "permission_denied": 2,
            "resource_not_found": 5
        }
        
        total_errors = sum(error_types.values())
        
        # Получение отчётов Ревы
        reva_reports = await self._fetch_reva_reports(period_hours)
        violations_by_target = {}
        reva_feedback = []
        for report in reva_reports:
            if report.get("event_type") != "review_completed":
                continue
            details = report.get("details", {})
            target = details.get("target")
            violations = details.get("violations", [])
            if target and violations:
                violations_by_target[target] = violations
                reva_feedback.append({
                    "target": target,
                    "violations": violations,
                    "timestamp": report.get("timestamp")
                })
        
        # Генерация гипотез на основе анализа
        generated_hypotheses = []
        recommendations = []
        
        if error_types.get("timeout", 0) > 10:
            generated_hypotheses.append("Увеличить таймауты в контейнерах с частыми timeout ошибками")
            recommendations.append("Проверить конфигурацию таймаутов в C0.1 и C6.2")
        
        if error_types.get("connection_error", 0) > 5:
            generated_hypotheses.append("Улучшить обработку сетевых ошибок и добавить retry логику")
            recommendations.append("Добавить exponential backoff для сетевых запросов")
        
        if total_errors > 20:
            generated_hypotheses.append("Провести аудит качества кода в контейнерах с наибольшим количеством ошибок")
            recommendations.append("Запустить статический анализ для C0.1, C6.2, C7.1")
        
        # Генерация гипотез на основе отчётов Ревы
        for target, violations in violations_by_target.items():
            for violation in violations:
                if violation.get("severity") == "error":
                    rule = violation.get("rule", "unknown")
                    generated_hypotheses.append(f"Исправить нарушение '{rule}' в {target} (отчёт Ревы)")
                    recommendations.append(f"Проверить {target} на соответствие правилу '{rule}'")
                elif violation.get("severity") == "warning":
                    rule = violation.get("rule", "unknown")
                    generated_hypotheses.append(f"Рассмотреть предупреждение '{rule}' в {target} (отчёт Ревы)")
                    recommendations.append(f"Оценить важность предупреждения '{rule}' в {target}")
        
        # Определение контейнеров с проблемами
        containers_with_issues = []
        if container_filter:
            containers_with_issues = [container_filter]
        else:
            # В реальной реализации будет анализ по контейнерам из логов
            containers_with_issues = ["C0.1", "C6.2", "C7.1", "C10.1"]
        
        # Поиск в векторной памяти для каждой значимой ошибки
        evidence_by_error = {}
        for error_type, count in error_types.items():
            if count > 5:  # значимая ошибка
                query = f"ошибка {error_type} в контейнерах завода"
                results = await self._search_memory(query)
                if results:
                    evidence_by_error[error_type] = results[:2]
        
        # Поиск лучших практик на GitHub для значимых ошибок
        github_evidence = {}
        for error_type, count in error_types.items():
            if count > 5:
                query = self._build_github_query(error_type)  # например: "docker timeout healthcheck best practices"
                results = await self._search_github(query)
                if results:
                    github_evidence[error_type] = results
        
        analysis_duration = time.time() - start_time
        
        report = AnalysisReport(
            period_start=period_start,
            period_end=period_end,
            total_logs_analyzed=1500,  # Имитация
            error_count=total_errors,
            error_types=error_types,
            containers_with_issues=containers_with_issues,
            generated_hypotheses=generated_hypotheses,
            recommendations=recommendations,
            analysis_duration_seconds=analysis_duration,
            evidence=evidence_by_error,  # новое поле
            reva_feedback=reva_feedback,  # отчёты Ревы
            github_evidence=github_evidence  # GitHub доказательства
        )
        
        # Логирование в BR18 (заглушка)
        logger.info(f"Анализ завершён: {total_errors} ошибок за {period_hours} часов")
        
        return report
    
    async def create_hypothesis_task(self, hypothesis_text: str, priority: str = "medium", 
                                   related_containers: Optional[List[str]] = None) -> HypothesisTask:
        """
        Создаёт задачу на основе гипотезы и отправляет в handover (BR7/C7.2)
        """
        if related_containers is None:
            related_containers = []
        
        hypothesis_id = str(uuid.uuid4())[:8]
        created_at = datetime.now()
        
        # Создаём задачу в handover
        handover_task_id = await self._create_handover_task(
            hypothesis_id=hypothesis_id,
            hypothesis_text=hypothesis_text,
            priority=priority,
            related_containers=related_containers
        )
        
        # Определяем, кому назначить задачу
        assigned_to = self._determine_assignee(hypothesis_text, priority)
        
        task = HypothesisTask(
            hypothesis_id=hypothesis_id,
            hypothesis_text=hypothesis_text,
            priority=priority,
            created_at=created_at,
            status="pending",
            assigned_to=assigned_to,
            handover_task_id=handover_task_id
        )
        
        self.hypothesis_tasks[hypothesis_id] = task
        
        # Логирование
        logger.info(f"Создана гипотеза {hypothesis_id}: {hypothesis_text[:50]}...")
        
        return task
    
    async def _create_handover_task(self, hypothesis_id: str, hypothesis_text: str, priority: str, 
                                  related_containers: List[str]) -> Optional[str]:
        """
        Создаёт задачу в handover системе (BR7/C7.2) через HTTP API
        """
        try:
            task_id = f"HYP-{hypothesis_id}"
            handover_url = f"{self.handover_url}/take"
            
            request_body = {
                "task_id": task_id,
                "actor": "АРХИ",
                "comment": f"Гипотеза Дедала: {hypothesis_text[:200]}"
            }
            
            logger.info(f"Отправка задачи в handover: {handover_url}, тело: {request_body}")
            response = await self.client.post(handover_url, json=request_body, timeout=10.0)
            response.raise_for_status()
            
            result = response.json()
            if result.get("success") is True:
                logger.info(f"Задача успешно создана в handover: {task_id}")
                # Логирование в BR18 (заглушка)
                await self._send_log_to_br18("handover_task_created", {
                    "task_id": task_id,
                    "hypothesis_id": hypothesis_id
                })
                return task_id
            else:
                logger.error(f"Handover вернул success=false: {result}")
                return None
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP ошибка при создании задачи в handover: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Ошибка сети при создании задачи в handover: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при создании задачи в handover: {e}")
            return None
    
    async def _search_memory(self, query: str, limit: int = 5) -> List[dict]:
        """Выполняет семантический поиск в векторной памяти C2.6.
        
        Args:
            query: Поисковый запрос (например, "ошибка timeout в контейнере C20.3")
            limit: Максимальное количество результатов
            
        Returns:
            Список результатов с полями: path, score, snippet, metadata
        """
        if not self.project_memory_url:
            return []
        url = f"{self.project_memory_url}/search"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json={"query": query, "limit": limit},
                    timeout=5.0
                )
                response.raise_for_status()
                data = response.json()
                return data.get("results", [])
        except Exception as e:
            logger.warning(f"C2.6 search failed for query '{query}': {e}")
            return []
    
    async def _search_github(self, query: str, limit: int = 3) -> List[dict]:
        """Поиск репозиториев на GitHub по запросу."""
        if not self.github_api_enabled:
            return []
        headers = {"Accept": "application/vnd.github.v3+json"}
        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={limit}"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                results = []
                for item in items:
                    results.append({
                        "name": item.get("full_name"),
                        "url": item.get("html_url"),
                        "stars": item.get("stargazers_count"),
                        "description": item.get("description", ""),
                        "language": item.get("language")
                    })
                logger.info(f"GitHub search for '{query}' returned {len(results)} results")
                return results
        except Exception as e:
            logger.warning(f"GitHub API error: {e}")
            return []
    
    def _build_github_query(self, error_type: str) -> str:
        """Формирует поисковый запрос для GitHub на основе типа ошибки."""
        queries = {
            "timeout": "docker timeout healthcheck best practices",
            "connection_error": "httpx retry async best practices",
            "validation_error": "pydantic validation best practices",
            "permission_denied": "docker permission denied fix",
            "resource_not_found": "fastapi 404 error handling"
        }
        return queries.get(error_type, f"{error_type} best practices python")
    
    async def _fetch_rss_feeds(self) -> List[dict]:
        """Читает RSS-ленты и возвращает список статей."""
        import feedparser
        results = []
        for feed_info in self.rss_feeds:
            url = feed_info.get("url")
            name = feed_info.get("name")
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries[:5]:
                    results.append({
                        "source": "rss",
                        "source_name": name,
                        "title": entry.get("title"),
                        "url": entry.get("link"),
                        "summary": entry.get("summary", "")[:500],
                        "published": entry.get("published")
                    })
            except Exception as e:
                logger.warning(f"RSS feed {url} failed: {e}")
        return results
    
    async def _fetch_arxiv(self) -> List[dict]:
        """Читает arXiv и возвращает список статей."""
        if not self.arxiv_enabled:
            return []
        import xml.etree.ElementTree as ET
        results = []
        for cat in self.arxiv_categories:
            url = f"http://export.arxiv.org/api/query?search_query=cat:{cat}&sortBy=submittedDate&sortOrder=descending&max_results=5"
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(url, timeout=15.0)
                    response.raise_for_status()
                    root = ET.fromstring(response.text)
                    ns = {"atom": "http://www.w3.org/2005/Atom"}
                    for entry in root.findall("atom:entry", ns):
                        title = entry.find("atom:title", ns).text
                        link = entry.find("atom:id", ns).text
                        summary = entry.find("atom:summary", ns).text[:500]
                        published = entry.find("atom:published", ns).text
                        results.append({
                            "source": "arxiv",
                            "source_name": f"arXiv {cat}",
                            "title": title,
                            "url": link,
                            "summary": summary,
                            "published": published
                        })
            except Exception as e:
                logger.warning(f"arXiv API for {cat} failed: {e}")
        return results
    
    async def _index_external_article(self, article: dict) -> None:
        """Индексирует внешнюю статью в C2.6."""
        import hashlib
        doc_id = f"ext_{hashlib.md5(article['url'].encode()).hexdigest()[:16]}"
        content = f"{article['title']}\n\n{article['summary']}"
        metadata = {
            "source": article["source"],
            "source_name": article["source_name"],
            "url": article["url"],
            "title": article["title"],
            "date": article.get("published", "")
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.project_memory_url}/index",
                    json={"documents": [{"id": doc_id, "content": content, "metadata": metadata}]},
                    timeout=10.0
                )
            logger.info(f"Indexed external article: {article['title'][:50]}")
        except Exception as e:
            logger.warning(f"Failed to index external article: {e}")
    
    async def _fetch_external_sources(self) -> List[dict]:
        """Собирает статьи из всех внешних источников (RSS + arXiv)."""
        rss_items = await self._fetch_rss_feeds()
        arxiv_items = await self._fetch_arxiv()
        all_items = rss_items + arxiv_items
        
        # Загружаем кэш уже обработанных URL
        processed_urls = set()
        if self.external_cache_file.exists():
            try:
                with open(self.external_cache_file, "r") as f:
                    processed_urls = set(json.load(f))
            except:
                pass
        
        # Фильтруем новые статьи
        new_items = []
        for item in all_items:
            if item["url"] not in processed_urls:
                new_items.append(item)
                processed_urls.add(item["url"])
        
        # Сохраняем обновлённый кэш
        with open(self.external_cache_file, "w") as f:
            json.dump(list(processed_urls), f)
        
        return new_items
    
    async def _fetch_reva_reports(self, period_hours: int = 24) -> List[dict]:
        """Читает отчёты Ревы (заглушка – из локального файла)."""
        if not self.use_reva_stub:
            # В будущем здесь будет реальный вызов API C6.2
            return []
        if not self.reva_reports_path.exists():
            return []
        try:
            with open(self.reva_reports_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            cutoff = datetime.now() - timedelta(hours=period_hours)
            reports = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    report = json.loads(line)
                    ts = datetime.fromisoformat(report.get("timestamp", "").replace("Z", "+00:00"))
                    if ts > cutoff:
                        reports.append(report)
                except Exception as e:
                    logger.warning(f"Failed to parse report line: {e}")
            return reports
        except Exception as e:
            logger.warning(f"Failed to read reva reports: {e}")
            return []
    
    def _determine_assignee(self, hypothesis_text: str, priority: str) -> str:
        """
        Определяет, кому назначить задачу (Cline или Гефест)
        """
        text_lower = hypothesis_text.lower()
        
        # Эвристики для определения назначения
        if any(word in text_lower for word in ["код", "рефакторинг", "баг", "ошибка", "тест"]):
            return "Cline"
        elif any(word in text_lower for word in ["инфраструктура", "docker", "deploy", "ci/cd", "конфигурация"]):
            return "Гефест"
        elif priority in ["high", "critical"]:
            return "Cline"  # Критические задачи назначаем Cline
        else:
            return "Cline"  # По умолчанию Cline
    
    async def _send_log_to_br18(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        Отправляет лог в BR18 (заглушка)
        В реальной реализации будет HTTP запрос к BR18 API
        """
        logger.info(f"BR18 лог: {event_type} - {data}")
        # В реальной реализации:
        # await self.client.post(self.br18_logs_url, json={
        #     "event_type": event_type,
        #     "data": data,
        #     "timestamp": datetime.now().isoformat(),
        #     "source": "C1.1"
        # })
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Возвращает статус healthcheck"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        
        # Проверка зависимостей (заглушки)
        dependencies_status = {
            "BR18": "available",  # В реальности проверять доступность
            "BR7": "available",
            "internal": "ok"
        }
        
        return {
            "status": "healthy",
            "version": "1.0.0",
            "dependencies": dependencies_status,
            "uptime_seconds": uptime,
            "hypothesis_tasks_count": len(self.hypothesis_tasks)
        }
    
    async def get_hypothesis_task(self, hypothesis_id: str) -> Optional[HypothesisTask]:
        """Получает задачу по ID"""
        return self.hypothesis_tasks.get(hypothesis_id)
    
    async def list_hypothesis_tasks(self, status: Optional[str] = None) -> List[HypothesisTask]:
        """Список задач гипотез"""
        if status:
            return [task for task in self.hypothesis_tasks.values() if task.status == status]
        return list(self.hypothesis_tasks.values())
    
    async def approve_hypothesis(self, hypothesis_id: str, comment: Optional[str] = None) -> dict:
        """Утвердить гипотезу и создать задачу в handover."""
        task = self.hypothesis_tasks.get(hypothesis_id)
        if not task:
            raise ValueError(f"Hypothesis {hypothesis_id} not found")
        if task.status != "pending":
            raise ValueError(f"Hypothesis already {task.status}")
        
        # Если уже есть handover_task_id, не создаём повторно
        if task.handover_task_id:
            handover_task_id = task.handover_task_id
        else:
            # Создаём задачу в handover (вызываем существующий метод)
            new_task = await self.create_hypothesis_task(
                hypothesis_text=task.hypothesis_text,
                priority=task.priority,
                related_containers=[]  # можно расширить, если нужно
            )
            handover_task_id = new_task.handover_task_id
            # Обновляем существующий объект
            task.handover_task_id = handover_task_id
        
        task.status = "approved"
        # Логируем в BR18
        await self._send_log_to_br18("hypothesis_approved", {
            "hypothesis_id": hypothesis_id,
            "handover_task_id": handover_task_id,
            "comment": comment
        })
        return {"status": "approved", "handover_task_id": handover_task_id}

    async def reject_hypothesis(self, hypothesis_id: str, reason: str) -> dict:
        """Отклонить гипотезу с указанием причины."""
        task = self.hypothesis_tasks.get(hypothesis_id)
        if not task:
            raise ValueError(f"Hypothesis {hypothesis_id} not found")
        if task.status != "pending":
            raise ValueError(f"Hypothesis already {task.status}")
        
        task.status = "rejected"
        task.rejection_reason = reason  # нужно добавить поле в модель HypothesisTask
        await self._send_log_to_br18("hypothesis_rejected", {
            "hypothesis_id": hypothesis_id,
            "reason": reason
        })
        return {"status": "rejected", "reason": reason}

    async def run_daily_analysis(self) -> str:
        """Запускает анализ и сохраняет отчёт в файл. Возвращает имя файла."""
        logger.info("Running scheduled daily analysis")
        
        # Сбор внешних источников (делаем это до анализа, чтобы можно было добавить в отчёт)
        external_articles = await self._fetch_external_sources()
        for article in external_articles:
            await self._index_external_article(article)
        
        # Анализ логов
        report = await self.analyze_logs(period_hours=24, container_filter=None)
        
        # Добавляем внешние статьи в отчёт
        report.external_insights = [ExternalArticle(**a) for a in external_articles]
        
        filename = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.reports_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report.dict(), f, indent=2, default=str, ensure_ascii=False)
        logger.info(f"Daily report saved: {filepath}")
        
        # Отправка события в BR18 (заглушка)
        await self._send_log_to_br18("daily_analysis_completed", {"report_file": filename})
        return filename

    async def close(self):
        """Закрытие ресурсов"""
        await self.client.aclose()


async def get_ab_version(object_type: str, object_id: str, context: Optional[str] = None) -> Optional[str]:
    """
    Запрашивает у C19.4 версию для объекта (prompt/skill).
    Возвращает строку версии или None, если эксперимента нет или C19.4 недоступен.
    """
    url = f"http://localhost:8106/api/version/{object_type}/{object_id}"
    if context:
        url += f"?context={context}"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("version")
    except Exception as e:
        # логировать ошибку, но не падать
        print(f"[AB] Failed to get version: {e}")
    return None


async def send_ab_metric(experiment_id: str, variant: str, success: bool, duration_ms: int, cost_usd: float = 0.0, context: str = ""):
    """Отправляет метрику в C19.4"""
    url = "http://localhost:8106/api/metrics"
    payload = {
        "experiment_id": experiment_id,
        "variant": variant,
        "success": success,
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "context": context
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        print(f"[AB] Failed to send metric: {e}")
