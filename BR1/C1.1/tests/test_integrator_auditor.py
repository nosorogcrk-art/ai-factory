import pytest
import json
from unittest.mock import AsyncMock, patch, mock_open
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrator_auditor import (
    get_integrator_stats_and_errors,
    get_tasks_summary,
    call_integrator_audit_skill,
    run_integrator_audit
)

@pytest.fixture
def mock_log_file():
    log_content = """2026-04-07 10:00:00 - INFO - "POST /build HTTP/1.1" 200 - task_id=task-123
2026-04-07 10:01:00 - ERROR - "POST /build HTTP/1.1" 500 - task_id=task-456 patch_id=PATCH-001
2026-04-07 10:02:00 - ERROR - Conflict detected in patch PATCH-002 - task_id=task-789
2026-04-07 10:03:00 - INFO - "POST /build HTTP/1.1" 200 - task_id=task-999
"""
    return log_content

@pytest.fixture
def mock_registry_file():
    registry = [
        {"id": "task-123", "status": "completed", "dependencies": []},
        {"id": "task-456", "status": "failed", "dependencies": ["task-123"]},
        {"id": "task-789", "status": "pending", "dependencies": ["task-456"]}
    ]
    return json.dumps(registry)

def test_get_integrator_stats_and_errors_success(mock_log_file):
    with patch("builtins.open", mock_open(read_data=mock_log_file)):
        with patch("pathlib.Path.exists", return_value=True):
            result = get_integrator_stats_and_errors(since_days=7)
    
    assert result["success_count"] == 2
    assert result["failure_count"] == 2
    assert "500" in result["top_error_types"]
    assert "conflict" in result["top_error_types"]
    assert len(result["error_samples"]) == 2

def test_get_integrator_stats_and_errors_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        result = get_integrator_stats_and_errors()
    
    assert result["success_count"] == 0
    assert result["failure_count"] == 0
    assert result["top_error_types"] == []
    assert result["error_samples"] == []

def test_get_tasks_summary_success(mock_registry_file):
    with patch("builtins.open", mock_open(read_data=mock_registry_file)):
        with patch("pathlib.Path.exists", return_value=True):
            result = get_tasks_summary(limit=5)
    
    assert len(result) == 3
    assert result[0]["id"] == "task-123"
    assert result[0]["status"] == "completed"
    assert result[1]["dependencies"] == ["task-123"]

def test_get_tasks_summary_file_not_found():
    with patch("pathlib.Path.exists", return_value=False):
        result = get_tasks_summary()
    
    assert result == []

@pytest.mark.asyncio
async def test_call_integrator_audit_skill_success():
    mock_response = {
        "result": {
            "analysis": "Анализ показал частые ошибки 500",
            "recommendations": ["Увеличить таймауты", "Добавить ретраи"],
            "risk_level": "medium"
        }
    }
    
    mock_resp = AsyncMock()
    mock_resp.status_code = 200
    mock_resp.json = AsyncMock(return_value=mock_response)
    mock_resp.raise_for_status = AsyncMock()
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=mock_resp)):
        result = await call_integrator_audit_skill()
    
    assert result is not None
    assert result["analysis"] == "Анализ показал частые ошибки 500"
    assert len(result["recommendations"]) == 2
    assert result["risk_level"] == "medium"

@pytest.mark.asyncio
async def test_call_integrator_audit_skill_failure():
    with patch("httpx.AsyncClient.post", AsyncMock(side_effect=Exception("Connection error"))):
        result = await call_integrator_audit_skill()
    
    assert result is None

@pytest.mark.asyncio
async def test_call_integrator_audit_skill_no_result_field():
    mock_response = {"status": "ok"}  # нет поля result
    
    with patch("httpx.AsyncClient.post", AsyncMock(return_value=AsyncMock(
        status_code=200,
        json=AsyncMock(return_value=mock_response)
    ))):
        result = await call_integrator_audit_skill()
    
    assert result is None

@pytest.mark.asyncio
async def test_run_integrator_audit_success(tmp_path):
    mock_result = {
        "analysis": "Тестовый анализ",
        "recommendations": ["Рекомендация 1"],
        "risk_level": "low"
    }
    
    with patch("integrator_auditor.call_integrator_audit_skill", AsyncMock(return_value=mock_result)):
        with patch("integrator_auditor.AUDIT_DIR", tmp_path):
            result = await run_integrator_audit()
    
    assert result == mock_result
    report_files = list(tmp_path.glob("audit_*.json"))
    assert len(report_files) == 1
    
    with open(report_files[0], "r", encoding="utf-8") as f:
        report = json.load(f)
    
    assert report["analysis"] == "Тестовый анализ"
    assert report["recommendations"] == ["Рекомендация 1"]
    assert report["risk_level"] == "low"
    assert "timestamp" in report

@pytest.mark.asyncio
async def test_run_integrator_audit_failure(tmp_path):
    with patch("integrator_auditor.call_integrator_audit_skill", AsyncMock(return_value=None)):
        with patch("integrator_auditor.AUDIT_DIR", tmp_path):
            result = await run_integrator_audit()
    
    assert result["analysis"] == "Не удалось получить рекомендации"
    assert result["recommendations"] == []
    assert result["risk_level"] == "unknown"
    
    report_files = list(tmp_path.glob("audit_*.json"))
    assert len(report_files) == 1