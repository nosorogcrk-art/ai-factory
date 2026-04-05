from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_build_success(mocker):
    mocker.patch("services.build_patches", return_value=(True, "Build started"))
    response = client.post("/build", json={"task_id": "DIALOG-123", "patch_ids": ["IMP-001"], "check_skills": True, "run_tests": True})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "started"


def test_build_failure(mocker):
    mocker.patch("services.build_patches", return_value=(False, "Something went wrong"))
    response = client.post("/build", json={"task_id": "DIALOG-123", "patch_ids": ["IMP-001"], "check_skills": True, "run_tests": True})
    assert response.status_code == 500
    assert "Something went wrong" in response.text