import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_get_map():
    response = client.get("/map")
    assert response.status_code == 200
    data = response.json()
    assert 'branches' in data
    assert 'containers' in data
    assert 'patches' in data
    assert 'stats' in data

def test_get_branches():
    response = client.get("/branches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_containers():
    response = client.get("/containers")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_patches():
    response = client.get("/patches")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_stats():
    response = client.get("/stats")
    assert response.status_code == 200
    assert isinstance(response.json(), dict)