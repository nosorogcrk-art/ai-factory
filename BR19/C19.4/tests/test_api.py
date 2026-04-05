import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_experiment():
    data = {
        "name": "Test Exp",
        "description": "test",
        "variants": ["A", "B"],
        "weights": [0.5, 0.5]
    }
    response = client.post("/experiments", json=data)
    assert response.status_code == 200
    assert "id" in response.json()
    return response.json()["id"]

def test_get_experiment():
    exp_id = test_create_experiment()
    response = client.get(f"/experiments/{exp_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Exp"

def test_list_experiments():
    response = client.get("/experiments")
    assert response.status_code == 200
    assert "experiments" in response.json()

def test_assign_variant():
    exp_id = test_create_experiment()
    # сначала активируем эксперимент
    client.patch(f"/experiments/{exp_id}", json={"status": "active"})
    response = client.post(f"/experiments/{exp_id}/assign?user_id=user123")
    assert response.status_code == 200
    data = response.json()
    assert "variant" in data
    assert data["experiment_id"] == exp_id

def test_get_stats():
    exp_id = test_create_experiment()
    client.patch(f"/experiments/{exp_id}", json={"status": "active"})
    client.post(f"/experiments/{exp_id}/assign?user_id=user1")
    client.post(f"/experiments/{exp_id}/assign?user_id=user2")
    response = client.get(f"/experiments/{exp_id}/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total_assignments" in stats
    assert stats["total_assignments"] == 2

def test_update_experiment_status():
    exp_id = test_create_experiment()
    response = client.patch(f"/experiments/{exp_id}", json={"status": "active"})
    assert response.status_code == 200
    response = client.get(f"/experiments/{exp_id}")
    assert response.json()["status"] == "active"