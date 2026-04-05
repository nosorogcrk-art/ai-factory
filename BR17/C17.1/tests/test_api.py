import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_create_skill():
    skill_data = {
        "name": "Test Skill",
        "version": "1.0.0",
        "description": "A test skill",
        "author": "tester",
        "status": "draft",
        "tags": ["test"],
        "task_types": ["test"],
        "languages": ["python"],
        "allowed_for_swarm": False,
        "depends_on": [],
        "related_patches": [],
        "instruction": "print('hello')"
    }
    response = client.post("/skills", json=skill_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Skill"
    assert data["id"].startswith("SKILL-")
    return data["id"]

def test_get_skill():
    skill_id = test_create_skill()
    response = client.get(f"/skills/{skill_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == skill_id

def test_get_skills_list():
    response = client.get("/skills")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_update_skill():
    skill_id = test_create_skill()
    update_data = {"name": "Updated Skill"}
    response = client.patch(f"/skills/{skill_id}", json=update_data)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Skill"

def test_delete_skill():
    skill_id = test_create_skill()
    response = client.delete(f"/skills/{skill_id}")
    assert response.status_code == 200
    response = client.get(f"/skills/{skill_id}")
    assert response.status_code == 404

def test_get_stats():
    response = client.get("/skills/stats")
    assert response.status_code == 200
    stats = response.json()
    assert "total" in stats