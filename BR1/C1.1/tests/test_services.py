import json
import pytest
import httpx
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from ..services import CognitiveEngineService
from ..models import AnalysisReport, HypothesisTask


class TestCognitiveEngineService:
    """Тесты для сервиса когнитивного движка"""
    
    @pytest.fixture
    def service(self):
        return CognitiveEngineService()
    
    @pytest.mark.asyncio
    async def test_analyze_logs_basic(self, service):
        """Тест базового анализа логов"""
        report = await service.analyze_logs(period_hours=24)
        
        assert isinstance(report, AnalysisReport)
        assert report.period_hours == 24
        assert report.error_count > 0
        assert isinstance(report.error_types, dict)
        assert isinstance(report.generated_hypotheses, list)
        assert isinstance(report.recommendations, list)
        assert report.analysis_duration_seconds > 0
        
        # Проверяем, что период правильный
        time_diff = report.period_end - report.period_start
        assert timedelta(hours=23) < time_diff < timedelta(hours=25)
    
    @pytest.mark.asyncio
    async def test_analyze_logs_with_filter(self, service):
        """Тест анализа с фильтром контейнера"""
        report = await service.analyze_logs(period_hours=12, container_filter="C0.1")
        
        assert isinstance(report, AnalysisReport)
        assert "C0.1" in report.containers_with_issues
    
    @pytest.mark.asyncio
    async def test_create_hypothesis_task(self, service):
        """Тест создания задачи на основе гипотезы"""
        hypothesis_text = "Увеличить таймауты в контейнере C0.1 для уменьшения ошибок timeout"
        
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock) as mock_handover:
            mock_handover.return_value = "handover_task_12345"
            
            task = await service.create_hypothesis_task(
                hypothesis_text=hypothesis_text,
                priority="high",
                related_containers=["C0.1", "C6.2"]
            )
        
        assert isinstance(task, HypothesisTask)
        assert task.hypothesis_text == hypothesis_text
        assert task.priority == "high"
        assert task.assigned_to == "Cline"  # По эвристике для кода
        assert task.handover_task_id == "handover_task_12345"
        assert task.status == "pending"
        
        # Проверяем, что задача сохранена
        assert task.hypothesis_id in service.hypothesis_tasks
    
    @pytest.mark.asyncio
    async def test_create_hypothesis_task_infrastructure(self, service):
        """Тест создания задачи для инфраструктуры (должна быть назначена Гефесту)"""
        hypothesis_text = "Обновить конфигурацию Docker для улучшения производительности"
        
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock) as mock_handover:
            mock_handover.return_value = "handover_task_67890"
            
            task = await service.create_hypothesis_task(
                hypothesis_text=hypothesis_text,
                priority="medium"
            )
        
        assert task.assigned_to == "Гефест"  # По эвристике для инфраструктуры
    
    @pytest.mark.asyncio
    async def test_determine_assignee(self, service):
        """Тест определения назначения задачи"""
        # Код-задачи -> Cline
        assert service._determine_assignee("Исправить баг в коде", "medium") == "Cline"
        assert service._determine_assignee("Рефакторинг модуля", "low") == "Cline"
        assert service._determine_assignee("Добавить тесты", "medium") == "Cline"
        
        # Инфраструктурные задачи -> Гефест
        assert service._determine_assignee("Настроить Docker", "medium") == "Гефест"
        assert service._determine_assignee("Обновить CI/CD", "high") == "Гефест"
        
        # Критические задачи -> Cline
        assert service._determine_assignee("Любая задача", "critical") == "Cline"
        assert service._determine_assignee("Другая задача", "high") == "Cline"
        
        # По умолчанию -> Cline
        assert service._determine_assignee("Неизвестная задача", "low") == "Cline"
    
    @pytest.mark.asyncio
    async def test_get_health_status(self, service):
        """Тест healthcheck"""
        health_status = await service.get_health_status()
        
        assert health_status["status"] == "healthy"
        assert health_status["version"] == "1.0.0"
        assert "BR18" in health_status["dependencies"]
        assert "BR7" in health_status["dependencies"]
        assert health_status["uptime_seconds"] > 0
        assert "hypothesis_tasks_count" in health_status
    
    @pytest.mark.asyncio
    async def test_get_hypothesis_task(self, service):
        """Тест получения задачи по ID"""
        # Создаем задачу
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock):
            task = await service.create_hypothesis_task(
                hypothesis_text="Тестовая гипотеза",
                priority="medium"
            )
        
        # Получаем задачу
        retrieved_task = await service.get_hypothesis_task(task.hypothesis_id)
        
        assert retrieved_task is not None
        assert retrieved_task.hypothesis_id == task.hypothesis_id
        assert retrieved_task.hypothesis_text == task.hypothesis_text
    
    @pytest.mark.asyncio
    async def test_get_hypothesis_task_not_found(self, service):
        """Тест получения несуществующей задачи"""
        task = await service.get_hypothesis_task("non_existent_id")
        assert task is None
    
    @pytest.mark.asyncio
    async def test_list_hypothesis_tasks(self, service):
        """Тест списка задач"""
        # Создаем несколько задач
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock):
            task1 = await service.create_hypothesis_task("Гипотеза 1", "low")
            task2 = await service.create_hypothesis_task("Гипотеза 2", "medium")
        
        # Получаем все задачи
        all_tasks = await service.list_hypothesis_tasks()
        assert len(all_tasks) >= 2
        
        # Проверяем, что наши задачи в списке
        task_ids = [t.hypothesis_id for t in all_tasks]
        assert task1.hypothesis_id in task_ids
        assert task2.hypothesis_id in task_ids
    
    @pytest.mark.asyncio
    async def test_close(self, service):
        """Тест закрытия ресурсов"""
        # Просто проверяем, что метод существует и не падает
        await service.close()
        
        # После закрытия можно создать новый сервис
        new_service = CognitiveEngineService()
        assert new_service.client is not None
    
    @pytest.mark.asyncio
    async def test_create_handover_task_success(self, service):
        """Тест успешного создания задачи в handover через HTTP API"""
        hypothesis_id = "abc123"
        hypothesis_text = "Тестовая гипотеза для проверки handover API"
        priority = "medium"
        related_containers = ["C0.1", "C6.2"]
        
        expected_task_id = f"HYP-{hypothesis_id}"
        expected_url = f"{service.handover_url}/take"
        expected_body = {
            "task_id": expected_task_id,
            "actor": "АРХИ",
            "comment": f"Гипотеза Дедала: {hypothesis_text[:200]}"
        }
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "task_id": expected_task_id}
        
        with patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service._create_handover_task(
                hypothesis_id=hypothesis_id,
                hypothesis_text=hypothesis_text,
                priority=priority,
                related_containers=related_containers
            )
            
            # Проверяем, что запрос был отправлен с правильными параметрами
            mock_post.assert_called_once_with(
                expected_url,
                json=expected_body,
                timeout=10.0
            )
            
            # Проверяем результат
            assert result == expected_task_id
    
    @pytest.mark.asyncio
    async def test_create_handover_task_failure_success_false(self, service):
        """Тест создания задачи в handover, когда handover возвращает success=false"""
        hypothesis_id = "def456"
        hypothesis_text = "Еще одна тестовая гипотеза"
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False, "error": "Some error"}
        
        with patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await service._create_handover_task(
                hypothesis_id=hypothesis_id,
                hypothesis_text=hypothesis_text,
                priority="high",
                related_containers=[]
            )
            
            # Проверяем, что вернулся None
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_handover_task_http_error(self, service):
        """Тест создания задачи в handover при HTTP ошибке"""
        hypothesis_id = "ghi789"
        
        with patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.HTTPStatusError(
                "Error",
                request=MagicMock(),
                response=MagicMock(status_code=500, text="Internal Server Error")
            )
            
            result = await service._create_handover_task(
                hypothesis_id=hypothesis_id,
                hypothesis_text="Гипотеза с ошибкой",
                priority="medium",
                related_containers=[]
            )
            
            # Проверяем, что вернулся None при ошибке
            assert result is None
    
    @pytest.mark.asyncio
    async def test_create_handover_task_network_error(self, service):
        """Тест создания задачи в handover при сетевой ошибке"""
        hypothesis_id = "jkl012"
        
        with patch.object(service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.RequestError("Network error")
            
            result = await service._create_handover_task(
                hypothesis_id=hypothesis_id,
                hypothesis_text="Гипотеза с сетевой ошибкой",
                priority="low",
                related_containers=[]
            )
            
            # Проверяем, что вернулся None при сетевой ошибке
            assert result is None
    
    @pytest.mark.asyncio
    async def test_send_log_to_br18(self, service):
        """Тест отправки лога в BR18 (заглушка)"""
        event_type = "test_event"
        data = {"key": "value"}
        
        # Просто проверяем, что метод не падает
        service._send_log_to_br18(event_type, data)
        
        # В реальной реализации здесь будет проверка HTTP запроса

    @pytest.mark.asyncio
    async def test_approve_hypothesis_success(self, service):
        """Тест успешного утверждения гипотезы"""
        with patch.object(service, 'create_hypothesis_task', new_callable=AsyncMock) as mock_create:
            mock_create.return_value = HypothesisTask(
                hypothesis_id="test123",
                hypothesis_text="test",
                priority="medium",
                created_at=datetime.now(),
                handover_task_id="handover_123"
            )
            task = await service.create_hypothesis_task("test", "medium")
            result = await service.approve_hypothesis(task.hypothesis_id)
            assert result["status"] == "approved"
            assert task.status == "approved"

    @pytest.mark.asyncio
    async def test_reject_hypothesis_success(self, service):
        """Тест успешного отклонения гипотезы"""
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock) as mock_handover:
            mock_handover.return_value = "handover_task_123"
            task = await service.create_hypothesis_task("test", "medium")
            result = await service.reject_hypothesis(task.hypothesis_id, "not relevant")
            assert result["status"] == "rejected"
            assert task.status == "rejected"
            assert task.rejection_reason == "not relevant"

    @pytest.mark.asyncio
    async def test_approve_hypothesis_not_found(self, service):
        """Тест утверждения несуществующей гипотезы"""
        with pytest.raises(ValueError, match="Hypothesis not_found_id not found"):
            await service.approve_hypothesis("not_found_id")

    @pytest.mark.asyncio
    async def test_reject_hypothesis_not_found(self, service):
        """Тест отклонения несуществующей гипотезы"""
        with pytest.raises(ValueError, match="Hypothesis not_found_id not found"):
            await service.reject_hypothesis("not_found_id", "reason")

    @pytest.mark.asyncio
    async def test_approve_hypothesis_already_processed(self, service):
        """Тест утверждения уже обработанной гипотезы"""
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock) as mock_handover:
            mock_handover.return_value = "handover_task_123"
            task = await service.create_hypothesis_task("test", "medium")
            task.status = "approved"
            with pytest.raises(ValueError, match="Hypothesis already approved"):
                await service.approve_hypothesis(task.hypothesis_id)

    @pytest.mark.asyncio
    async def test_reject_hypothesis_already_processed(self, service):
        """Тест отклонения уже обработанной гипотезы"""
        with patch.object(service, '_create_handover_task', new_callable=AsyncMock) as mock_handover:
            mock_handover.return_value = "handover_task_123"
            task = await service.create_hypothesis_task("test", "medium")
            task.status = "rejected"
            with pytest.raises(ValueError, match="Hypothesis already rejected"):
                await service.reject_hypothesis(task.hypothesis_id, "reason")
    
    @pytest.mark.asyncio
    @patch("BR1.C1.1.services.CognitiveEngineService._search_memory")
    async def test_analyze_logs_calls_memory_search(self, mock_search, service):
        """Тест вызова поиска в векторной памяти при анализе логов"""
        mock_search.return_value = [{"path": "/test.md", "score": 0.9, "snippet": "Пример документа", "metadata": {}}]
        report = await service.analyze_logs(period_hours=24)
        
        # Проверяем, что метод поиска был вызван хотя бы один раз
        assert mock_search.called
        
        # Проверяем, что evidence добавилось в отчёт
        assert hasattr(report, "evidence")
        assert isinstance(report.evidence, dict)
        
        # Проверяем, что для значимых ошибок есть evidence
        # В тестовых данных timeout=15 и connection_error=8 > 5
        assert "timeout" in report.evidence or "connection_error" in report.evidence

    @pytest.mark.asyncio
    @patch("BR1.C1.1.services.CognitiveEngineService.analyze_logs")
    async def test_run_daily_analysis(self, mock_analyze, service, tmp_path):
        """Тест ежедневного анализа с сохранением отчёта"""
        # Подменяем reports_dir на временную папку
        service.reports_dir = tmp_path
        mock_report = MagicMock()
        mock_report.dict.return_value = {"test": "data", "error_count": 10}
        mock_analyze.return_value = mock_report
        
        filename = await service.run_daily_analysis()
        
        assert filename.startswith("report_")
        assert filename.endswith(".json")
        assert (tmp_path / filename).exists()
        mock_analyze.assert_called_once_with(period_hours=24, container_filter=None)
        
        # Проверяем содержимое файла
        with open(tmp_path / filename, "r", encoding="utf-8") as f:
            content = json.load(f)
            assert content["test"] == "data"
            assert content["error_count"] == 10
    
    @pytest.mark.asyncio
    async def test_fetch_reva_reports(self, service, tmp_path):
        """Тест получения отчётов Ревы"""
        service.reva_reports_path = tmp_path / "reva_reports.json"
        service.use_reva_stub = True
        
        # Создаём тестовый отчёт
        report_line = json.dumps({
            "timestamp": datetime.now().isoformat(),
            "event_type": "review_completed",
            "details": {"target": "C1.1.md", "violations": [{"rule": "has_tests", "severity": "error"}]}
        }) + "\n"
        service.reva_reports_path.write_text(report_line)
        
        reports = await service._fetch_reva_reports(24)
        assert len(reports) == 1
        assert reports[0]["details"]["target"] == "C1.1.md"
        assert reports[0]["event_type"] == "review_completed"
        assert reports[0]["details"]["violations"][0]["rule"] == "has_tests"
        assert reports[0]["details"]["violations"][0]["severity"] == "error"
    
    @pytest.mark.asyncio
    async def test_fetch_reva_reports_empty_file(self, service, tmp_path):
        """Тест получения отчётов Ревы из пустого файла"""
        service.reva_reports_path = tmp_path / "empty_reva_reports.json"
        service.use_reva_stub = True
        
        # Создаём пустой файл
        service.reva_reports_path.write_text("")
        
        reports = await service._fetch_reva_reports(24)
        assert len(reports) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_reva_reports_file_not_exists(self, service, tmp_path):
        """Тест получения отчётов Ревы при отсутствии файла"""
        service.reva_reports_path = tmp_path / "non_existent_reva_reports.json"
        service.use_reva_stub = True
        
        reports = await service._fetch_reva_reports(24)
        assert len(reports) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_reva_reports_stub_disabled(self, service):
        """Тест получения отчётов Ревы при отключенной заглушке"""
        service.use_reva_stub = False
        
        reports = await service._fetch_reva_reports(24)
        assert len(reports) == 0
    
    @pytest.mark.asyncio
    async def test_fetch_reva_reports_old_reports(self, service, tmp_path):
        """Тест получения только свежих отчётов Ревы"""
        service.reva_reports_path = tmp_path / "reva_reports.json"
        service.use_reva_stub = True
        
        # Создаём старый отчёт (48 часов назад)
        old_time = (datetime.now() - timedelta(hours=48)).isoformat()
        old_report_line = json.dumps({
            "timestamp": old_time,
            "event_type": "review_completed",
            "details": {"target": "old.md", "violations": [{"rule": "old_rule", "severity": "warning"}]}
        }) + "\n"
        
        # Создаём свежий отчёт (1 час назад)
        new_time = (datetime.now() - timedelta(hours=1)).isoformat()
        new_report_line = json.dumps({
            "timestamp": new_time,
            "event_type": "review_completed",
            "details": {"target": "new.md", "violations": [{"rule": "new_rule", "severity": "error"}]}
        }) + "\n"
        
        service.reva_reports_path.write_text(old_report_line + new_report_line)
        
        reports = await service._fetch_reva_reports(24)
        assert len(reports) == 1  # Только свежий отчёт
        assert reports[0]["details"]["target"] == "new.md"
    
    @pytest.mark.asyncio
    async def test_analyze_logs_includes_reva_feedback(self, service):
        """Тест, что анализ логов включает отчёты Ревы"""
        # Мокаем метод _fetch_reva_reports
        with patch.object(service, '_fetch_reva_reports', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = [
                {
                    "timestamp": datetime.now().isoformat(),
                    "event_type": "review_completed",
                    "details": {
                        "target": "C1.1.md",
                        "violations": [
                            {"rule": "has_tests", "severity": "error"},
                            {"rule": "has_docs", "severity": "warning"}
                        ]
                    }
                }
            ]
            
            report = await service.analyze_logs(period_hours=24)
            
            # Проверяем, что reva_feedback добавлено в отчёт
            assert hasattr(report, "reva_feedback")
            assert isinstance(report.reva_feedback, list)
            assert len(report.reva_feedback) == 1
            assert report.reva_feedback[0]["target"] == "C1.1.md"
            assert len(report.reva_feedback[0]["violations"]) == 2
            
            # Проверяем, что гипотезы сгенерированы на основе отчётов Ревы
            reva_hypotheses = [h for h in report.generated_hypotheses if "отчёт Ревы" in h]
            assert len(reva_hypotheses) >= 2  # Одна для error, одна для warning
    
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_search_github_success(self, mock_get, service):
        """Тест успешного поиска на GitHub"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "items": [
                {"full_name": "test/repo", "html_url": "https://github.com/test/repo", 
                 "stargazers_count": 100, "description": "test", "language": "Python"}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        service.github_api_enabled = True
        service.github_token = None
        
        results = await service._search_github("test query")
        
        assert len(results) == 1
        assert results[0]["name"] == "test/repo"
        assert results[0]["url"] == "https://github.com/test/repo"
        assert results[0]["stars"] == 100
        assert results[0]["description"] == "test"
        assert results[0]["language"] == "Python"
    
    @pytest.mark.asyncio
    async def test_search_github_disabled(self, service):
        """Тест поиска на GitHub при отключенном API"""
        service.github_api_enabled = False
        
        results = await service._search_github("test query")
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_search_github_error(self, mock_get, service):
        """Тест поиска на GitHub при ошибке API"""
        mock_get.side_effect = Exception("API error")
        
        service.github_api_enabled = True
        
        results = await service._search_github("test query")
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    async def test_build_github_query(self, service):
        """Тест формирования запроса для GitHub"""
        # Проверяем известные типы ошибок
        assert service._build_github_query("timeout") == "docker timeout healthcheck best practices"
        assert service._build_github_query("connection_error") == "httpx retry async best practices"
        assert service._build_github_query("validation_error") == "pydantic validation best practices"
        assert service._build_github_query("permission_denied") == "docker permission denied fix"
        assert service._build_github_query("resource_not_found") == "fastapi 404 error handling"
        
        # Проверяем неизвестный тип ошибки
        assert service._build_github_query("unknown_error") == "unknown_error best practices python"
    
    @pytest.mark.asyncio
    async def test_analyze_logs_includes_github_evidence(self, service):
        """Тест, что анализ логов включает GitHub доказательства"""
        # Мокаем метод _search_github
        with patch.object(service, '_search_github', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = [
                {"name": "test/repo", "url": "https://github.com/test/repo", "stars": 100, 
                 "description": "test", "language": "Python"}
            ]
            
            report = await service.analyze_logs(period_hours=24)
            
            # Проверяем, что github_evidence добавлено в отчёт
            assert hasattr(report, "github_evidence")
            assert isinstance(report.github_evidence, dict)
            
            # В тестовых данных timeout=15 и connection_error=8 > 5
            # Проверяем, что для этих ошибок есть GitHub доказательства
            if "timeout" in report.github_evidence:
                assert len(report.github_evidence["timeout"]) == 1
                assert report.github_evidence["timeout"][0]["name"] == "test/repo"
            
            if "connection_error" in report.github_evidence:
                assert len(report.github_evidence["connection_error"]) == 1
                assert report.github_evidence["connection_error"][0]["name"] == "test/repo"

    @pytest.mark.asyncio
    @patch("feedparser.parse")
    async def test_fetch_rss_feeds(self, mock_parse, service):
        """Тест получения RSS-лент"""
        mock_parse.return_value.entries = [
            {"title": "Test Article", "link": "http://test.com/article", 
             "summary": "Test summary", "published": "2026-04-05"}
        ]
        service.rss_feeds = [{"url": "http://test.com/rss", "name": "Test RSS"}]
        
        results = await service._fetch_rss_feeds()
        
        assert len(results) == 1
        assert results[0]["source"] == "rss"
        assert results[0]["source_name"] == "Test RSS"
        assert results[0]["title"] == "Test Article"
        assert results[0]["url"] == "http://test.com/article"
        assert results[0]["summary"] == "Test summary"
        assert results[0]["published"] == "2026-04-05"
        mock_parse.assert_called_once_with("http://test.com/rss")

    @pytest.mark.asyncio
    @patch("feedparser.parse")
    async def test_fetch_rss_feeds_empty(self, mock_parse, service):
        """Тест получения RSS-лент без записей"""
        mock_parse.return_value.entries = []
        service.rss_feeds = [{"url": "http://test.com/rss", "name": "Test RSS"}]
        
        results = await service._fetch_rss_feeds()
        
        assert len(results) == 0
        mock_parse.assert_called_once_with("http://test.com/rss")

    @pytest.mark.asyncio
    @patch("feedparser.parse")
    async def test_fetch_rss_feeds_error(self, mock_parse, service):
        """Тест получения RSS-лент с ошибкой"""
        mock_parse.side_effect = Exception("RSS error")
        service.rss_feeds = [{"url": "http://test.com/rss", "name": "Test RSS"}]
        
        results = await service._fetch_rss_feeds()
        
        assert len(results) == 0
        mock_parse.assert_called_once_with("http://test.com/rss")

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_fetch_arxiv(self, mock_get, service):
        """Тест получения статей из arXiv"""
        mock_response = MagicMock()
        mock_response.text = '''<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Test Article</title>
    <id>http://arxiv.org/abs/1234.5678</id>
    <summary>Test summary text</summary>
    <published>2026-04-05T00:00:00Z</published>
  </entry>
</feed>'''
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        service.arxiv_enabled = True
        service.arxiv_categories = ["cs.AI"]
        
        results = await service._fetch_arxiv()
        
        assert len(results) == 1
        assert results[0]["source"] == "arxiv"
        assert results[0]["source_name"] == "arXiv cs.AI"
        assert results[0]["title"] == "Test Article"
        assert results[0]["url"] == "http://arxiv.org/abs/1234.5678"
        assert results[0]["summary"] == "Test summary text"
        assert results[0]["published"] == "2026-04-05T00:00:00Z"

    @pytest.mark.asyncio
    async def test_fetch_arxiv_disabled(self, service):
        """Тест получения статей из arXiv при отключенном функционале"""
        service.arxiv_enabled = False
        
        results = await service._fetch_arxiv()
        
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.get")
    async def test_fetch_arxiv_error(self, mock_get, service):
        """Тест получения статей из arXiv с ошибкой"""
        mock_get.side_effect = Exception("arXiv API error")
        
        service.arxiv_enabled = True
        service.arxiv_categories = ["cs.AI"]
        
        results = await service._fetch_arxiv()
        
        assert len(results) == 0

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_index_external_article(self, mock_post, service):
        """Тест индексации внешней статьи"""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response
        
        article = {
            "source": "rss",
            "source_name": "Test RSS",
            "title": "Test Article",
            "url": "http://test.com/article",
            "summary": "Test summary",
            "published": "2026-04-05"
        }
        
        await service._index_external_article(article)
        
        # Проверяем, что запрос был отправлен
        assert mock_post.called
        call_args = mock_post.call_args
        assert "index" in call_args[0][0]  # URL содержит index
        json_data = call_args[1]["json"]
        assert "documents" in json_data
        assert len(json_data["documents"]) == 1
        assert json_data["documents"][0]["metadata"]["title"] == "Test Article"
        assert json_data["documents"][0]["metadata"]["url"] == "http://test.com/article"

    @pytest.mark.asyncio
    @patch("httpx.AsyncClient.post")
    async def test_index_external_article_error(self, mock_post, service):
        """Тест индексации внешней статьи с ошибкой"""
        mock_post.side_effect = Exception("Indexing error")
        
        article = {
            "source": "rss",
            "source_name": "Test RSS",
            "title": "Test Article",
            "url": "http://test.com/article",
            "summary": "Test summary",
            "published": "2026-04-05"
        }
        
        # Проверяем, что метод не падает при ошибке
        await service._index_external_article(article)

    @pytest.mark.asyncio
    @patch("BR1.C1.1.services.CognitiveEngineService._fetch_rss_feeds")
    @patch("BR1.C1.1.services.CognitiveEngineService._fetch_arxiv")
    async def test_fetch_external_sources(self, mock_arxiv, mock_rss, service, tmp_path):
        """Тест сбора внешних источников"""
        service.external_cache_file = tmp_path / "external_cache.json"
        
        # Настраиваем моки
        mock_rss.return_value = [
            {"source": "rss", "source_name": "Test RSS", "title": "RSS Article", 
             "url": "http://test.com/rss1", "summary": "RSS summary", "published": "2026-04-05"}
        ]
        mock_arxiv.return_value = [
            {"source": "arxiv", "source_name": "arXiv cs.AI", "title": "arXiv Article", 
             "url": "http://arxiv.org/abs/1234.5678", "summary": "arXiv summary", "published": "2026-04-05"}
        ]
        
        # Первый вызов - все статьи новые
        results = await service._fetch_external_sources()
        
        assert len(results) == 2
        assert results[0]["source"] == "rss"
        assert results[1]["source"] == "arxiv"
        
        # Проверяем, что кэш создан
        assert service.external_cache_file.exists()
        
        # Второй вызов - статьи уже в кэше, новых нет
        results2 = await service._fetch_external_sources()
        assert len(results2) == 0
        
        # Третий вызов с новой статьей
        mock_rss.return_value = [
            {"source": "rss", "source_name": "Test RSS", "title": "New RSS Article", 
             "url": "http://test.com/rss2", "summary": "New RSS summary", "published": "2026-04-06"}
        ]
        mock_arxiv.return_value = []
        
        results3 = await service._fetch_external_sources()
        assert len(results3) == 1
        assert results3[0]["title"] == "New RSS Article"

    @pytest.mark.asyncio
    @patch("BR1.C1.1.services.CognitiveEngineService._fetch_external_sources")
    @patch("BR1.C1.1.services.CognitiveEngineService._index_external_article")
    @patch("BR1.C1.1.services.CognitiveEngineService.analyze_logs")
    async def test_run_daily_analysis_includes_external_sources(self, mock_analyze, mock_index, mock_fetch, service, tmp_path):
        """Тест ежедневного анализа с внешними источниками"""
        service.reports_dir = tmp_path
        
        # Настраиваем моки
        mock_fetch.return_value = [
            {"source": "rss", "source_name": "Test RSS", "title": "Test Article", 
             "url": "http://test.com/article", "summary": "Test summary", "published": "2026-04-05"}
        ]
        mock_report = MagicMock()
        mock_report.dict.return_value = {"test": "data"}
        mock_analyze.return_value = mock_report
        
        filename = await service.run_daily_analysis()
        
        # Проверяем вызовы
        mock_fetch.assert_called_once()
        mock_index.assert_called_once()
        mock_analyze.assert_called_once_with(period_hours=24, container_filter=None)
        
        # Проверяем, что отчёт сохранён
        assert (tmp_path / filename).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
