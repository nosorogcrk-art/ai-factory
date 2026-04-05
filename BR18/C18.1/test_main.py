import pytest
from fastapi.testclient import TestClient
import json
import tempfile
import os
from datetime import datetime
import sys
from unittest.mock import patch

# Mock LOG_DIR before importing main
with patch.dict('os.environ', {'LOG_DIR': '/tmp/test_logs'}):
    from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_receive_single_log():
    log_data = {
        "timestamp": "2026-03-18T12:00:00Z",
        "service": "C7.2",
        "event_type": "handover_completed",
        "details": {
            "from_agent": "ГЕФЕСТ",
            "to_agent": "РЕВА",
            "task_id": "BR1-P01",
            "duration_ms": 3450,
            "status": "success"
        }
    }
    
    response = client.post("/api/logs", json=log_data)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "count": 1}

def test_receive_batch_logs():
    logs_data = [
        {
            "timestamp": "2026-03-18T12:00:00Z",
            "service": "C7.2",
            "event_type": "handover_completed",
            "details": {"task_id": "BR1-P01"}
        },
        {
            "timestamp": "2026-03-18T12:01:00Z",
            "service": "C6.1",
            "event_type": "chaos_test_started",
            "details": {"test_id": "chaos-001"}
        }
    ]
    
    response = client.post("/api/logs", json=logs_data)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "count": 2}

def test_invalid_timestamp():
    log_data = {
        "timestamp": "invalid-date",
        "service": "C7.2",
        "event_type": "handover_completed"
    }
    
    response = client.post("/api/logs", json=log_data)
    assert response.status_code == 400
    assert "errors" in response.json()["detail"]

def test_missing_required_fields():
    log_data = {
        "timestamp": "2026-03-18T12:00:00Z",
        # missing service
        "event_type": "handover_completed"
    }
    
    response = client.post("/api/logs", json=log_data)
    assert response.status_code == 400
    assert "errors" in response.json()["detail"]

def test_invalid_json():
    response = client.post("/api/logs", data="invalid json")
    assert response.status_code == 400
    assert "Invalid JSON" in response.json()["detail"]

def test_invalid_body_type():
    response = client.post("/api/logs", json="not an object or array")
    assert response.status_code == 400
    assert "Request body must be a JSON object or array" in response.json()["detail"]

def test_log_rotation():
    # This test would require mocking the date/time
    # For now, just test that the endpoint works
    log_data = {
        "timestamp": datetime.now().isoformat() + "Z",
        "service": "test",
        "event_type": "test_event"
    }
    
    response = client.post("/api/logs", json=log_data)
    assert response.status_code == 200
    assert response.json()["count"] == 1

if __name__ == "__main__":
    pytest.main([__file__, "-v"])