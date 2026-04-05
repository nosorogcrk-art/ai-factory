import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("database.get_repo")
def test_commit_skill(mock_get_repo):
    mock_repo = MagicMock()
    mock_commit = MagicMock()
    mock_commit.hexsha = "abc123"
    mock_repo.index.commit.return_value = mock_commit
    mock_get_repo.return_value = mock_repo
    response = client.post("/commit/SKILL-001", json={"content": {"name": "test"}, "message": "test commit"})
    assert response.status_code == 200
    data = response.json()
    assert "commit_hash" in data

@patch("database.get_repo")
def test_commit_skill_missing_content(mock_get_repo):
    response = client.post("/commit/SKILL-001", json={"message": "test"})
    assert response.status_code == 400
    assert "Missing content or message" in response.text

@patch("database.get_repo")
def test_get_history(mock_get_repo):
    mock_repo = MagicMock()
    mock_commit = MagicMock()
    mock_commit.hexsha = "abc123"
    mock_commit.author = "Test"
    mock_commit.committed_date = 1234567890
    mock_commit.message = "test message"
    mock_repo.iter_commits.return_value = [mock_commit]
    mock_get_repo.return_value = mock_repo
    response = client.get("/history/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["hash"] == "abc123"

@patch("database.get_repo")
def test_get_file(mock_get_repo):
    mock_repo = MagicMock()
    mock_repo.git.show.return_value = '{"name": "test"}'
    mock_get_repo.return_value = mock_repo
    response = client.get("/file/SKILL-001?ref=abc123")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "test"

@patch("database.get_repo")
def test_get_diff(mock_get_repo):
    mock_repo = MagicMock()
    mock_repo.git.diff.return_value = "diff content"
    mock_get_repo.return_value = mock_repo
    response = client.get("/diff/SKILL-001?from_hash=abc&to_hash=def")
    assert response.status_code == 200
    data = response.json()
    assert "diff" in data
    assert data["diff"] == "diff content"

@patch("database.get_repo")
@patch("database.get_file_content")
def test_rollback(mock_get_file_content, mock_get_repo):
    mock_repo = MagicMock()
    mock_commit = MagicMock()
    mock_commit.hexsha = "new123"
    mock_repo.index.commit.return_value = mock_commit
    mock_get_repo.return_value = mock_repo
    mock_get_file_content.return_value = {"name": "test"}
    response = client.post("/rollback/SKILL-001?to_hash=abc123")
    assert response.status_code == 200
    data = response.json()
    assert "new_commit_hash" in data
    assert data["new_commit_hash"] == "new123"