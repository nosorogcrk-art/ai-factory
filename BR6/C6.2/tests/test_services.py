import pytest
import tempfile
import os

from ..services import SemanticAuditor


@pytest.fixture
def auditor():
    return SemanticAuditor()


@pytest.mark.asyncio
async def test_review_file_success(auditor):
    """Тест успешной проверки файла с тестами и healthcheck"""
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
        
        # Проверяем файл
        response = await auditor.review_file(main_file)
        
        assert response.status in ["approved", "rework"]
        # Должно быть мало нарушений (только предупреждения от mypy/ruff)
        error_violations = [v for v in response.violations if v.severity == "error"]
        assert len(error_violations) == 0  # Не должно быть критических ошибок


@pytest.mark.asyncio
async def test_review_file_no_tests(auditor):
    """Тест проверки файла без тестов"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем основной файл без healthcheck
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        response = await auditor.review_file(main_file)
        
        assert response.status == "rework"
        # Должны быть нарушения
        assert len(response.violations) > 0
        # Должны быть предложения
        assert len(response.suggestions) > 0
        
        # Проверяем, что есть нарушение has_tests
        test_violations = [v for v in response.violations if v.rule == "has_tests"]
        assert len(test_violations) > 0


@pytest.mark.asyncio
async def test_review_file_no_healthcheck(auditor):
    """Тест проверки файла без healthcheck"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем папку tests
        test_dir = os.path.join(tmpdir, "tests")
        os.makedirs(test_dir)
        
        # Создаем тестовый файл
        test_file = os.path.join(test_dir, "test_example.py")
        with open(test_file, "w") as f:
            f.write("def test_example(): pass")
        
        # Создаем основной файл без healthcheck
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        # Создаем паспорт
        passport_file = os.path.join(tmpdir, "C6.2.md")
        with open(passport_file, "w") as f:
            f.write("# Паспорт контейнера")
        
        response = await auditor.review_file(main_file)
        
        # Должно быть нарушение has_healthcheck
        healthcheck_violations = [v for v in response.violations if v.rule == "has_healthcheck"]
        assert len(healthcheck_violations) > 0


@pytest.mark.asyncio
async def test_review_file_no_passport(auditor):
    """Тест проверки файла без паспорта"""
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
        
        # НЕ создаем паспорт
        
        response = await auditor.review_file(main_file)
        
        # Должно быть нарушение has_passport
        passport_violations = [v for v in response.violations if v.rule == "has_passport"]
        assert len(passport_violations) > 0


@pytest.mark.asyncio
async def test_review_file_not_found(auditor):
    """Тест проверки несуществующего файла"""
    response = await auditor.review_file("/nonexistent/path/to/file.py")
    
    assert response.status == "rework"
    assert len(response.violations) == 1  # Только file_exists
    assert response.violations[0].rule == "file_exists"
    assert response.violations[0].severity == "error"


@pytest.mark.asyncio
async def test_review_with_content(auditor):
    """Тест проверки с передачей контента"""
    python_code = """
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
"""
    
    response = await auditor.review_file("/dummy/path.py", content=python_code)
    
    assert response.status in ["approved", "rework"]
    # Должны быть нарушения (нет тестов, нет паспорта)
    assert len(response.violations) >= 2  # has_tests и has_passport как минимум


def test_check_has_tests(auditor):
    """Тест проверки наличия тестов"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Создаем папку tests
        test_dir = os.path.join(tmpdir, "tests")
        os.makedirs(test_dir)
        
        # Создаем тестовый файл
        test_file = os.path.join(test_dir, "test_example.py")
        with open(test_file, "w") as f:
            f.write("def test_example(): pass")
        
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        # Должно вернуть None (тесты есть)
        result = auditor._check_has_tests(main_file)
        assert result is None
        
        # Удаляем тестовый файл
        os.remove(test_file)
        result = auditor._check_has_tests(main_file)
        assert result == "Нет файлов тестов (test_*.py) в папке tests"
        
        # Удаляем папку tests
        os.rmdir(test_dir)
        result = auditor._check_has_tests(main_file)
        assert result == "Папка tests не найдена"


def test_check_has_healthcheck(auditor):
    """Тест проверки наличия healthcheck"""
    with tempfile.TemporaryDirectory() as tmpdir:
        main_file = os.path.join(tmpdir, "main.py")
        
        # Файл с healthcheck
        with open(main_file, "w") as f:
            f.write("""
from fastapi import FastAPI
app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}
""")
        
        result = auditor._check_has_healthcheck(main_file)
        assert result is None
        
        # Файл без healthcheck
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        result = auditor._check_has_healthcheck(main_file)
        assert result == "Не найден эндпоинт /health или healthcheck"


def test_check_has_passport(auditor):
    """Тест проверки наличия паспорта"""
    with tempfile.TemporaryDirectory() as tmpdir:
        main_file = os.path.join(tmpdir, "main.py")
        with open(main_file, "w") as f:
            f.write("print('Hello')")
        
        # Создаем паспорт
        passport_file = os.path.join(tmpdir, "C6.2.md")
        with open(passport_file, "w") as f:
            f.write("# Паспорт контейнера")
        
        result = auditor._check_has_passport(main_file)
        assert result is None
        
        # Удаляем паспорт
        os.remove(passport_file)
        result = auditor._check_has_passport(main_file)
        assert result == "Не найден паспорт контейнера C6.2.md"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])