import pytest
from fastapi import HTTPException
from services import create_project_service, add_message_service, add_artifact_service, delete_artifact_service

def test_create_project_success(mocker):
    mocker.patch("services.repo.name_exists_active", return_value=False)
    mocker.patch("services.repo.create_project")
    mocker.patch("services.create_metadata_file")
    result = create_project_service("Test", "Desc")
    assert result["name"] == "Test"
    assert result["status"] == "active"

def test_create_project_duplicate(mocker):
    mocker.patch("services.repo.name_exists_active", return_value=True)
    with pytest.raises(ValueError, match="already exists"):
        create_project_service("Test", "Desc")

def test_add_message_success(mocker):
    mocker.patch("services.repo.project_exists", return_value=True)
    mocker.patch("services.ensure_project_dir", return_value=True)
    mocker.patch("services.repo.insert_message", return_value=42)
    mocker.patch("services.add_to_chroma")
    result = add_message_service("proj_123", "user", "Hello", "text")
    assert result["id"] == 42

def test_add_artifact_success(mocker):
    mocker.patch("services.repo.project_exists", return_value=True)
    mocker.patch("services.ensure_project_dir", return_value=True)
    mocker.patch("services.repo.insert_artifact")
    mocker.patch("services.add_to_chroma")
    mocker.patch("builtins.open", mocker.mock_open())
    result = add_artifact_service("proj_123", "code", "test.py", "print('Hello')", "1.0")
    assert result["name"] == "test.py"
    assert result["artifact_type"] == "code"

def test_add_artifact_missing_project(mocker):
    mocker.patch("services.repo.project_exists", return_value=False)
    with pytest.raises(HTTPException) as exc:
        add_artifact_service("proj_999", "code", "test.py", "content", "1.0")
    assert exc.value.status_code == 404

def test_delete_artifact_service(mocker):
    mocker.patch("services.repo.project_exists", return_value=True)
    mocker.patch("services.repo.get_artifact_filename", return_value="file.txt")
    mock_delete = mocker.patch("services.repo.delete_artifact")
    mocker.patch("services.delete_from_chroma")
    mocker.patch("pathlib.Path.unlink")
    delete_artifact_service("proj_123", "art_123")
    mock_delete.assert_called_once_with("art_123")