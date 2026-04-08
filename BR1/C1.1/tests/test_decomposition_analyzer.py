import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decomposition_analyzer import (
    load_task_registry,
    parse_integrator_log,
    get_integrator_stats,
    call_decomposition_optimizer_skill,
    run_decomposition_analysis
)

def test_load_task_registry(tmp_path):
    """Тест загрузки реестра задач."""
    # Создаем временный файл реестра
    registry_file = tmp_path / "task_registry.json"
    registry_file.write_text(json.dumps([
        {"id": "task1", "history": []},
        {"id": "task2", "history": [{"to": "REWORK"}]}
    ]))
    with patch("decomposition_analyzer.TASK_REGISTRY_PATH", registry_file):
        tasks = load_task_registry()
        assert len(tasks) == 2
        assert tasks[0]["id"] == "task1"
        assert tasks[1]["id"] == "task2"

def test_load_task_registry_not_found():
    """Тест загрузки реестра, когда файл отсутствует."""
    with patch("decomposition_analyzer.TASK_REGISTRY_PATH", Path("/nonexistent.json")):
        tasks = load_task_registry()
        assert tasks == []

def test_parse_integrator_log(tmp_path):
    """Тест парсинга лога интегратора."""
    log_file = tmp_path / "integrator.log"
    log_content = '''172.18.0.4:42508 - "POST /build HTTP/1.1" 200 OK task_id=DIALOG-123
172.18.0.4:42509 - "POST /build HTTP/1.1" 500 Internal Server Error task_id=DIALOG-456
172.18.0.4:42510 - "POST /build HTTP/1.1" 200 OK task_id=DIALOG-789
'''
    log_file.write_text(log_content)
    with patch("decomposition_analyzer.INTEGRATOR_LOG_PATH", log_file):
        stats = parse_integrator_log(since_days=1)
        assert "DIALOG-123" in stats["success"]
        assert "DIALOG-456" in stats["failures"]
        assert "DIALOG-789" in stats["success"]
        assert len(stats["success"]) == 2
        assert len(stats["failures"]) == 1

def test_parse_integrator_log_not_found():
    """Тест парсинга лога, когда файл отсутствует."""
    with patch("decomposition_analyzer.INTEGRATOR_LOG_PATH", Path("/nonexistent.log")):
        stats = parse_integrator_log(since_days=1)
        assert stats == {"success": [], "failures": []}

def test_get_integrator_stats():
    """Тест сбора статистики интегратора."""
    with patch("decomposition_analyzer.parse_integrator_log", return_value={"success": ["task1", "task2"], "failures": ["task3"]}):
        stats = get_integrator_stats()
        assert stats["success_count"] == 2
        assert stats["failure_count"] == 1
        assert stats["top_error_types"] == []

@pytest.mark.asyncio
async def test_call_decomposition_optimizer_skill_success():
    """Тест успешного вызова навыка decomposition_optimizer."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"result": {"analysis": "ok", "rules": ["rule1"]}}
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
        result = await call_decomposition_optimizer_skill([], {})
        assert result is not None
        assert "analysis" in result
        assert "rules" in result
        assert result["analysis"] == "ok"
        assert result["rules"] == ["rule1"]

@pytest.mark.asyncio
async def test_call_decomposition_optimizer_skill_failure():
    """Тест вызова навыка с ошибкой соединения."""
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Connection error"))):
        result = await call_decomposition_optimizer_skill([], {})
        assert result is None

@pytest.mark.asyncio
async def test_call_decomposition_optimizer_skill_invalid_json():
    """Тест вызова навыка с некорректным JSON в ответе."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}  # нет поля result
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_response)):
        result = await call_decomposition_optimizer_skill([], {})
        assert result is None

@pytest.mark.asyncio
async def test_run_decomposition_analysis_success(tmp_path):
    """Тест основной функции анализа декомпозиции (успешный вызов навыка)."""
    mock_tasks = [{"id": "task1", "history": []}]
    mock_stats = {"success_count": 1, "failure_count": 0, "top_error_types": []}
    mock_skill_result = {"analysis": "Анализ выполнен", "rules": ["правило 1"]}
    
    with patch("decomposition_analyzer.load_task_registry", return_value=mock_tasks):
        with patch("decomposition_analyzer.get_integrator_stats", return_value=mock_stats):
            with patch("decomposition_analyzer.call_decomposition_optimizer_skill", AsyncMock(return_value=mock_skill_result)):
                with patch("decomposition_analyzer.ANALYSIS_DIR", tmp_path):
                    result = await run_decomposition_analysis()
                    # result - это результат навыка
                    assert result["analysis"] == "Анализ выполнен"
                    assert result["rules"] == ["правило 1"]
                    # Проверяем, что файлы созданы
                    report_files = list(tmp_path.glob("analysis_*.json"))
                    assert len(report_files) == 1
                    rules_file = tmp_path / "decomposition_rules.json"
                    assert rules_file.exists()
                    # Проверяем содержимое файла правил
                    with open(rules_file, "r", encoding="utf-8") as f:
                        rules_data = json.load(f)
                        assert "generated_at" in rules_data
                        assert "rules" in rules_data
                        assert rules_data["rules"] == ["правило 1"]

@pytest.mark.asyncio
async def test_run_decomposition_analysis_skill_failure(tmp_path):
    """Тест основной функции анализа декомпозиции (ошибка вызова навыка)."""
    mock_tasks = [{"id": "task1", "history": []}]
    mock_stats = {"success_count": 0, "failure_count": 0, "top_error_types": []}
    
    with patch("decomposition_analyzer.load_task_registry", return_value=mock_tasks):
        with patch("decomposition_analyzer.get_integrator_stats", return_value=mock_stats):
            with patch("decomposition_analyzer.call_decomposition_optimizer_skill", AsyncMock(return_value=None)):
                with patch("decomposition_analyzer.ANALYSIS_DIR", tmp_path):
                    result = await run_decomposition_analysis()
                    # result - это fallback результат
                    assert result["analysis"] == "Не удалось получить рекомендации"
                    assert result["rules"] == []
                    # Проверяем, что файлы созданы
                    report_files = list(tmp_path.glob("analysis_*.json"))
                    assert len(report_files) == 1
                    rules_file = tmp_path / "decomposition_rules.json"
                    assert rules_file.exists()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
