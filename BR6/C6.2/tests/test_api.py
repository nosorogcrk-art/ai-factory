import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
import tempfile
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app


client = TestClient(app)


def test_root_endpoint():
    """Тест корневого эндпоинта"""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "Semantic Auditor C6.2"
    assert data["status"] == "running"


def test_health_check():
    """Тест healthcheck эндпоинта"""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_get_rules():
    """Тест получения списка правил"""
    response = client.get("/rules")
    assert response.status_code == 200
    data = response.json()
    assert "rules" in data
    assert len(data["rules"]) > 0
    assert data["rules"][0]["name"] == "has_tests"


def test_review_success():
    """Тест успешной проверки файла"""
    # Создаем временный файл с тестами
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем папку tests
        test_dir = os.path.join(tmpdir, "tests")
        os.makedirs(test_dir)
        
        # Создаем тестовый файл
        test_file = os.path.join(test_dir, "test_example.py")
        with open(test_file, "w") as f:
            f.write("def test_example(): pass")
        
        # Создаем основной файл с healthcheck
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
""")
        
        # Создаем паспорт
        passport_file = os.path.join(tmpdir, "C6.2.md")
        with open(passport_file, "w") as f:
            f.write("# Паспорт контейнера")
        
        # Отправляем запрос на проверку
        response = client.post("/review", json={
            "file_path": main_file,
            "content": None
        })
        
        assert response.status_code == 200
        data = response.json()
        # Файл должен быть одобрен (или иметь только предупреждения)
        assert data["status"] in ["approved", "rework"]
        # Должны быть предложения если есть нарушения
        assert "suggestions" in data
        assert "violations" in data


def test_review_violation():
    """Тест проверки файла без тестов"""
    # Создаем временный файл без тестов
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем основной файл без healthcheck
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        response = client.post("/review", json={
            "file_path": main_file,
            "content": None
        })
        
        assert response.status_code == 200
        data = response.json()
        # Должны быть нарушения
        assert len(data["violations"]) > 0
        # Должны быть предложения
        assert len(data["suggestions"]) > 0


def test_review_file_not_found():
    """Тест проверки несуществующего файла"""
    response = client.post("/review", json={
        "file_path": "/nonexistent/path/to/file.py",
        "content": None
    })
    
    assert response.status_code == 200  # Возвращает 200 с ошибкой в ответе
    data = response.json()
    assert data["status"] == "rework"
    assert len(data["violations"]) > 0
    # Должно быть нарушение file_exists
    file_exists_violations = [v for v in data["violations"] if v["rule"] == "file_exists"]
    assert len(file_exists_violations) > 0


def test_review_with_content():
    """Тест проверки с передачей контента вместо файла"""
    python_code = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
"""
    
    response = client.post("/review", json={
        "file_path": "/dummy/path.py",  # Путь игнорируется когда есть content
        "content": python_code
    })
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "violations" in data
    assert "suggestions" in data


def test_invalid_json():
    """Тест с невалидным JSON"""
    response = client.post("/review", data="invalid json")
    assert response.status_code == 422  # Validation error


if __name__ == "__main__":
    pytest.main([__file__, "-v"])