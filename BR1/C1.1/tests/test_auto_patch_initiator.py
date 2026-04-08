import pytest
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from auto_patch_initiator import (
    should_create_task,
    build_task_payload,
    scan_reports,
    mark_report_processed,
    REPORT_DIRS
)

def test_should_create_task_high_risk():
    """Тест: задача должна создаваться при high risk_level."""
    report = {"risk_level": "high", "suggestions": []}
    assert should_create_task(report) is True

def test_should_create_task_with_suggestions():
    """Тест: задача должна создаваться при наличии suggestions."""
    report = {"risk_level": "low", "suggestions": ["improve prompt"]}
    assert should_create_task(report) is True

def test_should_create_task_with_recommendations():
    """Тест: задача должна создаваться при наличии recommendations."""
    report = {"risk_level": "low", "recommendations": ["fix something"]}
    assert should_create_task(report) is True

def test_should_create_task_skip():
    """Тест: задача не должна создаваться при low risk и пустых рекомендациях."""
    report = {"risk_level": "low", "suggestions": []}
    assert should_create_task(report) is False

def test_build_task_payload():
    """Тест: формирование payload для handover."""
    report_data = {
        "analysis": "test analysis with some details",
        "suggestions": ["fix prompt", "add example"],
        "risk_level": "high"
    }
    payload = build_task_payload(report_data, "prompt_analysis", Path("/fake/path/analysis_2026-04-08.json"))
    
    assert "Auto: Prompt Analysis – test analysis with some details" in payload["title"]
    assert "assigned_role" in payload
    assert payload["assigned_role"] == "ARCHITECT"
    assert payload["priority"] == "high"
    assert "fix prompt" in payload["description"]
    assert "Источник: /fake/path/analysis_2026-04-08.json" in payload["description"]
    assert payload["metadata"]["source"] == "daedalus_auto"
    assert payload["metadata"]["report_type"] == "prompt_analysis"
    assert payload["metadata"]["risk_level"] == "high"

def test_build_task_payload_medium_priority():
    """Тест: формирование payload с medium приоритетом."""
    report_data = {
        "analysis": "test",
        "suggestions": ["suggestion"],
        "risk_level": "medium"
    }
    payload = build_task_payload(report_data, "decomposition_analysis", Path("/fake/path"))
    assert payload["priority"] == "medium"
    assert payload["assigned_role"] == "ARCHITECT"

def test_build_task_payload_integrator_audit():
    """Тест: формирование payload для integrator_audit (должен быть HEPHESTUS)."""
    report_data = {
        "analysis": "integrator issues",
        "recommendations": ["fix integration"],
        "risk_level": "low"
    }
    payload = build_task_payload(report_data, "integrator_audit", Path("/fake/path"))
    assert payload["assigned_role"] == "HEPHESTUS"

@pytest.mark.asyncio
async def test_scan_reports(tmp_path):
    """Тест: сканирование отчётов с обработкой флагов."""
    # Создаём временную структуру отчётов
    report_dir = tmp_path / "prompt_analysis"
    report_dir.mkdir(parents=True)
    report_file = report_dir / "analysis_2026-04-08.json"
    report_file.write_text(json.dumps({"risk_level": "medium", "suggestions": []}))
    
    # Подменяем REPORT_DIRS
    with patch("auto_patch_initiator.REPORT_DIRS", {"prompt_analysis": report_dir}):
        reports = scan_reports()
        assert len(reports) == 1
        assert reports[0][0] == report_file
        assert reports[0][1] == "prompt_analysis"
        assert reports[0][2]["risk_level"] == "medium"
        
        # Помечаем как обработанный
        mark_report_processed(report_file)
        
        # Повторный вызов должен вернуть пустой список
        reports2 = scan_reports()
        assert len(reports2) == 0

def test_mark_report_processed(tmp_path):
    """Тест: создание файла-флага .processed."""
    report_file = tmp_path / "analysis_test.json"
    report_file.touch()
    
    mark_report_processed(report_file)
    
    processed_flag = report_file.with_suffix(report_file.suffix + ".processed")
    assert processed_flag.exists()

@pytest.mark.asyncio
async def test_run_auto_patch_initiation_no_reports():
    """Тест: запуск без отчётов."""
    from auto_patch_initiator import run_auto_patch_initiation
    
    with patch("auto_patch_initiator.scan_reports", return_value=[]):
        with patch("auto_patch_initiator.logger") as mock_logger:
            await run_auto_patch_initiation()
            # Проверяем, что был вызван лог "No new reports found"
            mock_logger.info.assert_any_call("No new reports found")

@pytest.mark.asyncio
async def test_run_auto_patch_initiation_with_task_creation():
    """Тест: запуск с созданием задачи."""
    from auto_patch_initiator import run_auto_patch_initiation, create_task_in_handover
    
    mock_report_data = {
        "risk_level": "high",
        "analysis": "critical issue",
        "suggestions": ["fix now"]
    }
    mock_report_path = Path("/fake/path/analysis_2026-04-08.json")
    
    with patch("auto_patch_initiator.scan_reports", return_value=[
        (mock_report_path, "prompt_analysis", mock_report_data)
    ]):
        with patch("auto_patch_initiator.create_task_in_handover", new_callable=AsyncMock) as mock_create:
            with patch("auto_patch_initiator.mark_report_processed") as mock_mark:
                mock_create.return_value = True
                
                await run_auto_patch_initiation()
                
                # Проверяем, что create_task_in_handover был вызван
                mock_create.assert_called_once()
                # Проверяем, что mark_report_processed был вызван
                mock_mark.assert_called_once_with(mock_report_path)

@pytest.mark.asyncio
async def test_run_auto_patch_initiation_skip_no_suggestions():
    """Тест: пропуск отчёта без рекомендаций."""
    from auto_patch_initiator import run_auto_patch_initiation
    
    mock_report_data = {
        "risk_level": "low",
        "analysis": "no issues",
        "suggestions": []
    }
    mock_report_path = Path("/fake/path/analysis_2026-04-08.json")
    
    with patch("auto_patch_initiator.scan_reports", return_value=[
        (mock_report_path, "prompt_analysis", mock_report_data)
    ]):
        with patch("auto_patch_initiator.create_task_in_handover", new_callable=AsyncMock) as mock_create:
            with patch("auto_patch_initiator.mark_report_processed") as mock_mark:
                with patch("auto_patch_initiator.logger") as mock_logger:
                    await run_auto_patch_initiation()
                    
                    # Проверяем, что create_task_in_handover НЕ был вызван
                    mock_create.assert_not_called()
                    # Проверяем, что mark_report_processed был вызван (всё равно помечаем как обработанный)
                    mock_mark.assert_called_once_with(mock_report_path)
                    # Проверяем лог о пропуске
                    mock_logger.info.assert_any_call(
                        f"Skipped (no high risk or suggestions): {mock_report_path}"
                    )

@pytest.mark.asyncio
async def test_create_task_in_handover_success():
    """Тест: успешное создание задачи в handover."""
    from auto_patch_initiator import create_task_in_handover
    
    payload = {"title": "Test task", "description": "Test"}
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        result = await create_task_in_handover(payload)
        
        assert result is True
        mock_client.post.assert_called_once()

@pytest.mark.asyncio
async def test_create_task_in_handover_failure():
    """Тест: ошибка при создании задачи в handover."""
    from auto_patch_initiator import create_task_in_handover
    
    payload = {"title": "Test task", "description": "Test"}
    
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        with patch("auto_patch_initiator.logger") as mock_logger:
            result = await create_task_in_handover(payload)
            
            assert result is False
            mock_logger.error.assert_called_once()