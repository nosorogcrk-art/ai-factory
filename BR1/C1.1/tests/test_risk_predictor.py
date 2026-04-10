import pytest
import json
import tempfile
import os
from unittest.mock import AsyncMock, patch, MagicMock
from auto_patch_initiator import calculate_risk_score, fetch_projects, scan_projects_for_risk, create_handover_task


def test_calculate_risk_score_low():
    """Тест низкого уровня риска (нет рекомендаций)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаём временные файлы отчётов без рекомендаций
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/prompt_analysis"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/decomposition_analysis"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/integrator_audit"), exist_ok=True)
        
        # Создаём отчёт без suggestions
        report_path = os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/prompt_analysis", "test_project_123.json")
        with open(report_path, "w") as f:
            json.dump({"analysis": "test", "suggestions": []}, f)
        
        # Мокаем glob.glob чтобы возвращать наши пути
        with patch("auto_patch_initiator.glob.glob") as mock_glob:
            mock_glob.side_effect = lambda pattern: [report_path] if "prompt_analysis" in pattern else []
            
            result = calculate_risk_score("test_project")
            assert result["risk_level"] == "low"
            assert result["risk_score"] == 0
            assert len(result["reasons"]) == 0


def test_calculate_risk_score_high():
    """Тест высокого уровня риска (есть рекомендации во всех трёх категориях)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/prompt_analysis"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/decomposition_analysis"), exist_ok=True)
        os.makedirs(os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/integrator_audit"), exist_ok=True)
        
        # Создаём отчёты с рекомендациями
        prompt_report = os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/prompt_analysis", "test_project_123.json")
        with open(prompt_report, "w") as f:
            json.dump({"analysis": "test", "suggestions": ["improve prompt"]}, f)
        
        decomp_report = os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/decomposition_analysis", "decomp_123.json")
        with open(decomp_report, "w") as f:
            json.dump({"generated_rules": ["правило требует доработки"]}, f)
        
        audit_report = os.path.join(tmpdir, "01_ЦЕХ/МЕТРИКИ/integrator_audit", "audit_123.json")
        with open(audit_report, "w") as f:
            json.dump({"recommendations": ["fix integration"]}, f)
        
        with patch("auto_patch_initiator.glob.glob") as mock_glob:
            def glob_side_effect(pattern):
                if "prompt_analysis" in pattern:
                    return [prompt_report]
                elif "decomposition_analysis" in pattern:
                    return [decomp_report]
                elif "integrator_audit" in pattern:
                    return [audit_report]
                return []
            mock_glob.side_effect = glob_side_effect
            
            result = calculate_risk_score("test_project")
            assert result["risk_level"] == "high"
            assert result["risk_score"] == 3
            assert len(result["reasons"]) == 3


@pytest.mark.asyncio
async def test_fetch_projects_success():
    """Тест успешного получения проектов из project-memory."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": "project1"}, {"id": "project2"}]
    
    with patch("auto_patch_initiator.httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.__aenter__.return_value.get.return_value = mock_response
        mock_client.return_value = mock_instance
        
        projects = await fetch_projects()
        assert len(projects) == 2
        assert projects[0]["id"] == "project1"
        assert projects[1]["id"] == "project2"


@pytest.mark.asyncio
async def test_scan_projects_for_risk_creates_task():
    """Тест создания задачи для high-risk проекта."""
    # Мокаем fetch_projects
    with patch("auto_patch_initiator.fetch_projects", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = [{"id": "high_risk_project"}]
        
        # Мокаем calculate_risk_score чтобы вернуть high risk
        with patch("auto_patch_initiator.calculate_risk_score") as mock_calc:
            mock_calc.return_value = {
                "risk_level": "high",
                "risk_score": 3,
                "reasons": ["reason1", "reason2"]
            }
            
            # Мокаем create_handover_task
            with patch("auto_patch_initiator.create_handover_task", new_callable=AsyncMock) as mock_create:
                mock_create.return_value = True
                
                # Мокаем os.makedirs и open для записи отчёта
                with patch("auto_patch_initiator.os.makedirs") as mock_makedirs, \
                     patch("auto_patch_initiator.open", create=True) as mock_open, \
                     patch("auto_patch_initiator.datetime") as mock_datetime:
                    
                    mock_datetime.now.return_value.isoformat.return_value = "2026-04-10T00:00:00"
                    mock_file = MagicMock()
                    mock_open.return_value.__enter__.return_value = mock_file
                    
                    await scan_projects_for_risk()
                    
                    # Проверяем, что create_handover_task был вызван с правильными аргументами
                    mock_create.assert_called_once()
                    call_args = mock_create.call_args
                    assert "Risk alert: project high_risk_project" in call_args[1]["title"]
                    assert "ARGUS" == call_args[1]["assigned_role"]
                    assert "high" == call_args[1]["priority"]


@pytest.mark.asyncio
async def test_trigger_endpoint():
    """Тест эндпоинта /trigger_risk_analysis (мок scan_projects_for_risk)."""
    from main import app
    from fastapi.testclient import TestClient
    
    with patch("main.scan_projects_for_risk", new_callable=AsyncMock) as mock_scan:
        mock_scan.return_value = None
        
        client = TestClient(app)
        response = client.post("/trigger_risk_analysis")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "message": "Risk analysis started"}
        mock_scan.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])