import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

@patch("main.graph.get_graph")
def test_get_graph(mock_get_graph):
    mock_get_graph.return_value = {"nodes": [], "edges": []}
    response = client.get("/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data

@patch("main.graph.skills_meta", {"SKILL-001": {"id": "SKILL-001", "name": "Test"}})
@patch("main.graph.outgoing", {"SKILL-001": []})
def test_get_skill_info():
    response = client.get("/graph/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert data["skill"]["id"] == "SKILL-001"

def test_get_skill_info_not_found():
    response = client.get("/graph/UNKNOWN")
    assert response.status_code == 404

@patch("main.graph.get_dependencies")
def test_get_dependencies(mock_get_deps):
    mock_get_deps.return_value = ["SKILL-002"]
    response = client.get("/dependencies/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert "dependencies" in data

@patch("main.graph.get_reverse_dependencies")
def test_get_reverse_dependencies(mock_get_rev):
    mock_get_rev.return_value = ["SKILL-003"]
    response = client.get("/reverse-dependencies/SKILL-001")
    assert response.status_code == 200
    data = response.json()
    assert "reverse_dependencies" in data

@patch("main.graph.detect_cycles")
def test_cycle_check(mock_detect):
    mock_detect.return_value = []
    response = client.get("/cycle-check")
    assert response.status_code == 200
    data = response.json()
    assert data["has_cycles"] is False