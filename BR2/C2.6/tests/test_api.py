from fastapi.testclient import TestClient
from main import app
import uuid

client = TestClient(app)

def test_create_project_api():
    name = f"Integration Test {uuid.uuid4().hex[:6]}"
    response = client.post("/projects", json={"name": name, "description": "Test"})
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["name"] == name

def test_get_project_list():
    response = client.get("/projects")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_add_message_api():
    name = f"Msg Project {uuid.uuid4().hex[:6]}"
    resp = client.post("/projects", json={"name": name, "description": "Test"})
    proj_id = resp.json()["id"]
    msg_resp = client.post(f"/projects/{proj_id}/messages", json={"role": "user", "content": "Hello", "message_type": "text"})
    assert msg_resp.status_code == 201
    data = msg_resp.json()
    assert data["content"] == "Hello"

def test_add_artifact_api():
    name = f"Artifact Test {uuid.uuid4().hex[:6]}"
    resp = client.post("/projects", json={"name": name, "description": "Test"})
    proj_id = resp.json()["id"]
    art_resp = client.post(f"/projects/{proj_id}/artifacts", json={
        "artifact_type": "code",
        "name": "test.py",
        "content": "print('Hello')",
        "version": "1.0"
    })
    assert art_resp.status_code == 201
    data = art_resp.json()
    assert data["name"] == "test.py"
    assert data["artifact_type"] == "code"

def test_get_artifact_content_api():
    name = f"Content Test {uuid.uuid4().hex[:6]}"
    resp = client.post("/projects", json={"name": name, "description": "Test"})
    proj_id = resp.json()["id"]
    art_resp = client.post(f"/projects/{proj_id}/artifacts", json={
        "artifact_type": "code",
        "name": "test.py",
        "content": "print('Hello')",
        "version": "1.0"
    })
    artifact_id = art_resp.json()["id"]
    content_resp = client.get(f"/projects/{proj_id}/artifacts/{artifact_id}/content")
    assert content_resp.status_code == 200
    assert content_resp.json()["content"] == "print('Hello')"

def test_delete_artifact_api():
    name = f"Delete Test {uuid.uuid4().hex[:6]}"
    resp = client.post("/projects", json={"name": name, "description": "Test"})
    proj_id = resp.json()["id"]
    art_resp = client.post(f"/projects/{proj_id}/artifacts", json={
        "artifact_type": "code",
        "name": "test.py",
        "content": "print('Hello')",
        "version": "1.0"
    })
    artifact_id = art_resp.json()["id"]
    delete_resp = client.delete(f"/projects/{proj_id}/artifacts/{artifact_id}")
    assert delete_resp.status_code == 204
    get_resp = client.get(f"/projects/{proj_id}/artifacts/{artifact_id}")
    assert get_resp.status_code == 404

def test_search_api():
    name = f"Search Test {uuid.uuid4().hex[:6]}"
    resp = client.post("/projects", json={"name": name, "description": "Test"})
    proj_id = resp.json()["id"]
    client.post(f"/projects/{proj_id}/messages", json={"role": "user", "content": "Hello, world!", "message_type": "text"})
    search_resp = client.post(f"/projects/{proj_id}/search", json={"query": "hello", "n_results": 5})
    assert search_resp.status_code == 200
    data = search_resp.json()
    assert "results" in data

def test_search_project_not_found():
    response = client.post("/projects/nonexistent/search", json={"query": "test", "n_results": 5})
    assert response.status_code == 404