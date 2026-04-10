import sys
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))
from main import app

client = TestClient(app)

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

def test_index():
    r = client.post("/index", json={"documents": ["BR1/C1.1/C1.1.md"]})
    assert r.status_code == 200
    assert "indexed_count" in r.json()