import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, mock_open, call, Mock
from ab_auto_accept import (
    fetch_winning_experiments, update_skill, update_prompt,
    apply_new_version, is_experiment_processed, mark_experiment_processed
)

@pytest.mark.asyncio
async def test_fetch_winning_experiments_success():
    mock_response = Mock()
    mock_response.json.return_value = {"experiments": [{"id": "exp1"}]}
    mock_response.raise_for_status = Mock()
    with patch("httpx.AsyncClient.get", return_value=mock_response):
        experiments = await fetch_winning_experiments()
        assert len(experiments) == 1

def test_update_skill(tmp_path, monkeypatch):
    # Перенаправляем SKILLS_BASE_DIR во временную папку
    temp_skills = tmp_path / "skills"
    temp_skills.mkdir()
    skill_dir = temp_skills / "test_skill"
    skill_dir.mkdir()
    prompt_file = skill_dir / "prompt.md"
    prompt_file.write_text("old content")
    monkeypatch.setattr("ab_auto_accept.SKILLS_BASE_DIR", temp_skills)
    update_skill("test_skill", "new content")
    assert prompt_file.read_text() == "new content"
    assert (prompt_file.with_suffix(".md.bak")).exists()

def test_update_prompt(tmp_path, monkeypatch):
    temp_prompts = tmp_path / "prompts"
    temp_prompts.mkdir()
    prompt_file = temp_prompts / "test_prompt.md"
    prompt_file.write_text("old")
    monkeypatch.setattr("ab_auto_accept.PROMPTS_BASE_DIR", temp_prompts)
    update_prompt("test_prompt", "new")
    assert prompt_file.read_text() == "new"

@pytest.mark.asyncio
async def test_apply_new_version_skill(tmp_path, monkeypatch):
    # Мокаем update_skill и проверяем вызов
    experiment = {
        "id": "exp1",
        "object_type": "skill",
        "object_id": "test_skill",
        "result": {
            "p_value": 0.01,
            "improvement": 0.1,
            "treatment_rate": 0.8,
            "control_rate": 0.7,
            "new_content": "new prompt content"
        }
    }
    mock_update = AsyncMock()
    monkeypatch.setattr("ab_auto_accept.update_skill", mock_update)
    result = await apply_new_version(experiment)
    assert result["status"] == "accepted"
    assert result["winner"] == "treatment"
    mock_update.assert_called_with("test_skill", "new prompt content")

def test_mark_processed(tmp_path, monkeypatch):
    monkeypatch.setattr("ab_auto_accept.ACCEPTED_MARK_DIR", tmp_path)
    exp_id = "exp123"
    assert not is_experiment_processed(exp_id)
    mark_experiment_processed(exp_id)
    assert is_experiment_processed(exp_id)