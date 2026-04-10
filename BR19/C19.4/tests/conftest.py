import os
import sys
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Добавляем родительскую директорию в sys.path для импорта main
sys.path.insert(0, str(Path(__file__).parent.parent))

# Создаём временный файл базы данных
tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
tmp_db.close()
os.environ["DB_PATH"] = tmp_db.name

from main import app, init_db

# Принудительно инициализируем базу данных
init_db()

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    # Удаляем временный файл после тестов
    try:
        os.unlink(tmp_db.name)
    except:
        pass
