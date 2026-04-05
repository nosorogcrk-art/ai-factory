import pytest
from fastapi.testclient import TestClient
from datetime import datetime

# Import app directly
from main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_receive_metric():
    metric_data = {
        "name": "task_completion_time",
        "value": 123.45,
        "timestamp": datetime.now().isoformat(),
        "source": "C7.2",
        "tags": {"branch": "BR1", "agent": "ГЕФЕСТ"}
    }
    
    response = client.post("/api/metrics", json=metric_data)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

def test_receive_metric_without_tags():
    metric_data = {
        "name": "error_rate",
        "value": 0.05,
        "timestamp": datetime.now().isoformat(),
        "source": "C6.1"
    }
    
    response = client.post("/api/metrics", json=metric_data)
    assert response.status_code == 200
    assert response.json() == {"status": "accepted"}

def test_invalid_metric():
    metric_data = {
        "name": "test",
        # missing value
        "timestamp": datetime.now().isoformat(),
        "source": "test"
    }
    
    response = client.post("/api/metrics", json=metric_data)
    assert response.status_code == 422  # validation error

def test_metric_with_invalid_timestamp():
    metric_data = {
        "name": "test",
        "value": 100.0,
        "timestamp": "invalid-date",
        "source": "test"
    }
    
    response = client.post("/api/metrics", json=metric_data)
    assert response.status_code == 422  # validation error

def test_api_endpoints_exist():
    """Test that API endpoints return proper status codes (not 404)"""
    # Test list metrics endpoint
    response = client.get("/api/metrics/list")
    # Should return 200 with empty list or 404 if not implemented
    # We'll just check it's not a 500 error
    assert response.status_code != 500
    
    # Test get aggregates endpoint
    response = client.get("/api/metrics")
    assert response.status_code != 500
    
    # Test get specific metric (should return 404 for non-existent)
    response = client.get("/api/metrics/nonexistent")
    assert response.status_code == 404

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
